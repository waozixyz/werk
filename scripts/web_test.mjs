// Exercise the built site's Werkzeug app in a private headless browser with a
// disposable profile: the home screen, a tool opened by clicking Home and by
// ?app=, Calculator typing, Clock, and every tool in embedded mini mode.
import {spawn, spawnSync} from 'node:child_process';
import {readFile, writeFile, mkdir, mkdtemp} from 'node:fs/promises';
import {createServer} from 'node:http';
import {resolve, join, extname} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';

const root = resolve('build/site');
const output = resolve('build/web-test');
await mkdir(output, {recursive: true});
const profile = await mkdtemp(join(output, 'profile-'));
const types = {'.js': 'application/javascript', '.wasm': 'application/wasm', '.html': 'text/html',
  '.webmanifest': 'application/manifest+json', '.json': 'application/json', '.png': 'image/png'};
const server = createServer(async (request, response) => {
  const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
  const file = join(root, pathname.endsWith('/') ? pathname + 'index.html' : pathname);
  if (!file.startsWith(root + '/')) {
    response.writeHead(403).end();
    return;
  }
  try {
    const data = await readFile(file);
    response.setHeader('Content-Type', types[extname(file)] || 'application/octet-stream');
    response.end(data);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
const base = `http://127.0.0.1:${server.address().port}/app/`;
const environment = {...process.env};
for (const key of ['DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS']) delete environment[key];
const browser = spawn(process.env.WERK_WEB_BROWSER || 'chromium', ['--headless=new', '--no-sandbox',
  '--disable-gpu', '--disable-dev-shm-usage', '--no-first-run', '--remote-debugging-port=0',
  '--user-data-dir=' + profile, '--window-size=420,760', 'about:blank'],
  {env: environment, detached: true, stdio: ['ignore', 'ignore', 'pipe']});
let diagnostics = '';
browser.stderr.on('data', data => diagnostics = (diagnostics + data).slice(-4000));
let socket;
try {
  let port;
  const started = Date.now() + 30000;
  while (Date.now() < started) {
    try {
      port = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0];
      break;
    } catch {}
    await delay(100);
  }
  if (!port) throw Error('Chromium did not start: ' + diagnostics);
  // The DevTools port can open before Chromium registers its first tab.
  let page;
  const listed = Date.now() + 10000;
  while (!page && Date.now() < listed) {
    const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    page = targets.find(target => target.type === 'page');
    if (!page) await delay(100);
  }
  if (!page) throw Error('Chromium opened no page: ' + diagnostics);
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((done, fail) => {
    socket.addEventListener('open', done, {once: true});
    socket.addEventListener('error', fail, {once: true});
  });
  let sequence = 0;
  const pending = new Map();
  const exceptions = [];
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') exceptions.push(JSON.stringify(message.params.exceptionDetails));
    if (message.method === 'Runtime.consoleAPICalled') diagnostics += JSON.stringify(message.params.args);
    if (pending.has(message.id)) {
      pending.get(message.id)(message);
      pending.delete(message.id);
    }
  });
  const command = async (method, params = {}) => {
    const id = ++sequence;
    const answer = new Promise(done => pending.set(id, done));
    socket.send(JSON.stringify({id, method, params}));
    const result = await answer;
    if (result.error) throw Error(JSON.stringify(result.error));
    return result.result;
  };
  const evaluate = async expression => {
    const result = await command('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
    if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  const screenshot = async name => {
    const shot = await command('Page.captureScreenshot', {format: 'png'});
    await writeFile(join(output, name + '.png'), Buffer.from(shot.data, 'base64'));
  };
  const expectText = async (name, expected) => {
    await screenshot(name);
    let result = spawnSync('tesseract', [join(output, name + '.png'), 'stdout', '--psm', '11'],
      {env: environment, encoding: 'utf8', timeout: 20000});
    if (result.status !== 0) throw Error('Screenshot OCR failed: ' + result.stderr);
    if (!result.stdout.toLowerCase().includes(expected.toLowerCase())) {
      const readable = join(output, name + '-labels.png');
      const prepared = spawnSync('convert', [join(output, name + '.png'), '-colorspace', 'Gray',
        '-threshold', '55%', '-resize', '300%', readable], {env: environment, encoding: 'utf8'});
      if (prepared.status !== 0) throw Error('Could not prepare UI text: ' + prepared.stderr);
      result = spawnSync('tesseract', [readable, 'stdout', '--psm', '11'],
        {env: environment, encoding: 'utf8', timeout: 20000});
      if (result.status !== 0) throw Error('Screenshot OCR failed: ' + result.stderr);
    }
    if (!result.stdout.toLowerCase().includes(expected.toLowerCase()))
      throw Error(`${name}: expected ${expected}, saw ${result.stdout}`);
  };
  const click = async (x, y) => {
    await command('Input.dispatchMouseEvent', {type: 'mousePressed', x, y, button: 'left', clickCount: 1});
    await command('Input.dispatchMouseEvent', {type: 'mouseReleased', x, y, button: 'left', clickCount: 1});
    await delay(350);
  };
  const clickText = async label => {
    await screenshot('control');
    const readable = join(output, 'control-labels.png');
    const prepared = spawnSync('convert', [join(output, 'control.png'), '-colorspace', 'Gray',
      '-threshold', '55%', '-resize', '300%', readable], {env: environment, encoding: 'utf8'});
    if (prepared.status !== 0) throw Error('Could not prepare UI text: ' + prepared.stderr);
    const result = spawnSync('tesseract', [readable, 'stdout', '--psm', '11',
      '-c', 'tessedit_create_tsv=1'], {env: environment, encoding: 'utf8', timeout: 20000});
    if (result.status !== 0) throw Error('Screenshot OCR failed: ' + result.stderr);
    const rows = result.stdout.trim().split('\n').slice(1).map(line => line.split('\t'));
    const row = rows.find(values => values[11]?.trim() === label);
    if (!row) throw Error('Missing visible app control: ' + label);
    await click((Number(row[6]) + Number(row[8]) / 2) / 3,
      (Number(row[7]) + Number(row[9]) / 2) / 3);
  };
  // The canvas has drawn a frame with something besides the background.
  const painted = `(() => {
    const canvas = document.querySelector('canvas');
    if (!canvas || !canvas.width) return false;
    const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, Math.min(canvas.height, 200)).data;
    for (let i = 4; i < pixels.length; i += 4)
      if (pixels[i] !== pixels[0] || pixels[i + 1] !== pixels[1] || pixels[i + 2] !== pixels[2]) return true;
    return false;
  })()`;
  const open = async (query, name) => {
    await command('Page.navigate', {url: base + query});
    const until = Date.now() + 40000;
    while (Date.now() < until) {
      try {
        if (await evaluate(painted)) {
          await delay(500);
          await screenshot(name);
          return;
        }
      } catch {}
      await delay(200);
    }
    await screenshot(name + '-failure');
    throw Error(`Werkzeug did not draw ${query || 'home'}: ${exceptions.join(' ')} ${diagnostics}`);
  };
  const type = async text => {
    for (const character of text) {
      await command('Input.dispatchKeyEvent', {type: 'keyDown', text: character, key: character});
      await command('Input.dispatchKeyEvent', {type: 'keyUp', key: character});
      await delay(60);
    }
  };
  await command('Runtime.enable');
  await command('Page.enable');
  await command('Page.addScriptToEvaluateOnNewDocument', {source: `
    window.__timezoneReads = 0;
    const getTimezoneOffset = Date.prototype.getTimezoneOffset;
    Date.prototype.getTimezoneOffset = function() {
      window.__timezoneReads++;
      return getTimezoneOffset.call(this);
    };
  `});
  await command('Emulation.setDeviceMetricsOverride', {width: 420, height: 760, deviceScaleFactor: 1, mobile: false});
  await open('', 'home');
  const timezoneReadsBefore = await evaluate('window.__timezoneReads');
  await click(330, 92); // Shared List view.
  await clickText('Clock');
  await expectText('home-clock', 'Clock');
  await delay(1200);
  const timezoneReads = (await evaluate('window.__timezoneReads')) - timezoneReadsBefore;
  if (timezoneReads > 6) throw Error(`Clock read the time zone ${timezoneReads} times in 1.2 seconds`);
  await click(28, 28);
  await expectText('home-returned', 'Werkzeug');
  await open('?app=calculator', 'calculator');
  await type('12+30*2=');
  await delay(400);
  await expectText('calculator-typed', '72');
  // Clock also opens directly, where a broken time binding froze the page.
  await open('?app=clock', 'clock');
  // The embedded mini version opens on Home with every tool; a tool
  // would show its own name as the title.
  await open('?mini', 'mini-home');
  await expectText('mini-home', 'Werkzeug');
  for (const app of ['pass', 'auth', 'calculator', 'clock']) {
    await open('?mini&app=' + app, app + '-mini-direct');
    await expectText(app + '-mini-direct', app);
    await click(28, 28);
    await expectText(app + '-mini-home', 'Werkzeug');
    await clickText(app[0].toUpperCase() + app.slice(1));
    await expectText(app + '-mini-reopened', app);
  }
  await command('Emulation.setDeviceMetricsOverride', {width: 280, height: 480, deviceScaleFactor: 1, mobile: false});
  await open('?mini&app=unknown', 'mini-narrow-home');
  await expectText('mini-narrow-home', 'Find an app');
  await click(100, 92);
  await type('clock');
  await clickText('Clock');
  await expectText('mini-narrow-clock', 'Clock');
  await click(28, 28);
  await click(250, 28);
  await expectText('mini-narrow-profile', 'Profile');
  if (exceptions.length) throw Error('Page exceptions: ' + exceptions.join(' '));
  console.log('Werkzeug web: Calculator result, every mini tool, Home, Profile and narrow navigation verified in private Chromium');
} finally {
  socket?.close();
  try {
    process.kill(-browser.pid);
  } catch {}
  server.close();
}
