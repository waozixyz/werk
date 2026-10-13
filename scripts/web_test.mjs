// Exercise the built site's Werk app in a private headless browser with a
// disposable profile: the home screen, a tool opened by ?app=, Calculator
// typing, and Pass alone by ?mini as embedding pages use it.
import {spawn} from 'node:child_process';
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
  const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  socket = new WebSocket(pages.find(page => page.type === 'page').webSocketDebuggerUrl);
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
    throw Error(`Werk did not draw ${query || 'home'}: ${exceptions.join(' ')} ${diagnostics}`);
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
  await open('', 'home');
  await open('?app=calculator', 'calculator');
  await type('12+30*2=');
  await delay(400);
  await screenshot('calculator-typed');
  await open('?mini', 'pass-mini');
  if (exceptions.length) throw Error('Page exceptions: ' + exceptions.join(' '));
  console.log('Werk web: home, Calculator and Pass in mini mode drew in a private headless browser');
} finally {
  socket?.close();
  try {
    process.kill(-browser.pid);
  } catch {}
  server.close();
}
