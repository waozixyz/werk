"""Exercise the Workbook bundle on the caller's private Xvfb display."""
from pathlib import Path
import csv
import gzip
import io
import os
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from PIL import Image

assert os.environ.get('WERK_TEST_PRIVATE_DISPLAY') == '1', 'Use private Xvfb'
root = Path(__file__).resolve().parents[1]
work = root / 'build/workbook-gui-test'
shutil.rmtree(work, ignore_errors=True)
for directory in ('home', 'data/profile', 'cache', 'bin'):
    (work / directory).mkdir(parents=True, exist_ok=True)
(work / 'data/profile/settings.txt').write_text('theme_mode=1\n')
selector = work / 'selection.txt'
fake = work / 'bin/zenity'
fake.write_text('#!/bin/sh\ncat "$WORKBOOK_TEST_SELECTION"\n')
fake.chmod(0o700)
fixture = work / 'source.gnumeric'
fixture.write_text('''<?xml version="1.0"?><gnm:Workbook xmlns:gnm="http://www.gnumeric.org/v10.dtd"><gnm:SheetNameIndex><gnm:SheetName>Fixture</gnm:SheetName></gnm:SheetNameIndex><gnm:Sheets><gnm:Sheet><gnm:Name>Fixture</gnm:Name><gnm:MaxCol>1</gnm:MaxCol><gnm:MaxRow>0</gnm:MaxRow><gnm:Cells><gnm:Cell Row="0" Col="0" ValueType="40">11</gnm:Cell><gnm:Cell Row="0" Col="1">=A1*3</gnm:Cell></gnm:Cells></gnm:Sheet></gnm:Sheets></gnm:Workbook>''')
original = fixture.read_bytes()
env = dict(os.environ, HOME=str(work/'home'), WERK_DATA=str(work/'data'),
           XDG_CACHE_HOME=str(work/'cache'), XDG_CONFIG_HOME=str(work/'home/.config'),
           XDG_DATA_HOME=str(work/'home/.local/share'), ENTITY_DATA=str(work/'entity'),
           WERK_ASSETS=os.environ.get('WERK_TEST_ASSETS', str(root/'build')), WORKBOOK_TEST_SELECTION=str(selector),
           PATH=str(work/'bin')+':'+os.environ['PATH'])
app = None
window = None

def command(*args):
    return subprocess.check_output(args, env=env, text=True, timeout=20)

def start():
    global app, window
    app = subprocess.Popen([os.environ.get('WERK_TEST_APP', str(root/'build/werk')), '--app', 'workbook'], env=env)
    for _ in range(100):
        assert app.poll() is None, f'Werkzeug exited with status {app.returncode}'
        found = subprocess.run(['xdotool','search','--onlyvisible','--pid',str(app.pid)], env=env, capture_output=True, text=True)
        if found.returncode == 0:
            window = found.stdout.splitlines()[0]
            command('xdotool','windowsize',window,'960','600')
            command('xdotool','windowfocus','--sync',window)
            time.sleep(.6)
            return
        time.sleep(.1)
    raise AssertionError('No private Workbook window')

def stop():
    if app and app.poll() is None:
        app.terminate()
        app.wait(timeout=10)

def click(x,y):
    command('xdotool','mousemove','--window',window,str(x),str(y))
    time.sleep(.1)
    command('xdotool','click','1')
    time.sleep(.35)

def key(value):
    command('xdotool','key','--clearmodifiers',value)
    time.sleep(.3)

def type_text(value):
    command('xdotool','type','--clearmodifiers','--delay','30',value)
    time.sleep(.3)

def cell(path,row=0,col=0):
    data = path.read_bytes()
    if data[:2] == b'\x1f\x8b': data = gzip.decompress(data)
    doc = ET.fromstring(data)
    for item in doc.iter('{http://www.gnumeric.org/v10.dtd}Cell'):
        if item.get('Row') == str(row) and item.get('Col') == str(col): return item.text or ''
    return ''

saved = work/'data/apps/workbook/documents/workbook.gnumeric'
def expect(value,row=0,col=0,path=saved):
    for _ in range(80):
        if path.exists() and cell(path,row,col) == value: return
        time.sleep(.1)
    raise AssertionError(f'Missing saved fixture value {value!r}')

def menu(word):
    click(28,68)
    picture = work/'menu.png'
    command('import','-window',window,str(picture))
    # Isolate the popup so spreadsheet grid lines do not dominate OCR.
    target = work/'menu-labels.png'
    factor = 3
    with Image.open(picture) as image:
        popup = image.crop((0,82,175,195))
        popup.resize((popup.width*factor,popup.height*factor)).save(target)
    text = command('tesseract',str(target),'stdout','--psm','6','-c','tessedit_create_tsv=1')
    for item in csv.DictReader(io.StringIO(text), delimiter='\t'):
        if word.lower() in item['text'].lower():
            click((int(item['left'])+int(item['width'])//2)//factor,
                  82+(int(item['top'])+int(item['height'])//2)//factor)
            return
    raise AssertionError('Missing menu command '+word)

try:
    start()
    selection_picture = work/'selection.png'
    command('import','-window',window,str(selection_picture))
    with Image.open(selection_picture) as image:
        pixels = image.convert('RGB')
        assert pixels.getpixel((88,177)) != pixels.getpixel((184,177)), 'Selected cell needs a visible fill'
        assert pixels.getpixel((40,177)) != pixels.getpixel((184,177)), 'Selected cell needs a visible outline'
        assert pixels.getpixel((88,154)) != pixels.getpixel((184,177)), 'Headers need to be distinct from cells'
    click(88,177)
    type_text('5'); key('Return'); expect('5')
    key('ctrl+z'); expect('')
    key('ctrl+y'); expect('5')
    bundle = work/'downloaded.zx'
    selector.write_text(str(bundle)+'\n')
    menu('Download')
    for _ in range(50):
        if bundle.exists(): break
        time.sleep(.1)
    assert bundle.read_bytes() == (root/'build/apps/workbook.zx').read_bytes(), 'Downloaded bytes differ'
    selector.write_text(str(fixture)+'\n')
    menu('Open')
    expect('11'); expect('=A1*3',col=1)
    assert fixture.read_bytes() == original, 'Import changed the chosen source'
    exported = work/'export.gnumeric'
    selector.write_text(str(exported)+'\n')
    menu('As')
    expect('11',path=exported); expect('=A1*3',col=1,path=exported)
    invalid = work/'invalid.gnumeric'
    invalid.write_text('invalid spreadsheet fixture')
    selector.write_text(str(invalid)+'\n')
    menu('Open')
    time.sleep(.5)
    expect('11'); expect('=A1*3',col=1)
    click(88,177); type_text('7'); key('Return'); expect('7')
    command('import','-window',window,str(work/'workbook.png'))
    stop(); start()
    click(88,199); type_text('9'); key('Return'); expect('9',row=1)
    expect('7')
    assert saved.stat().st_mode & 0o777 == 0o600
    print('Workbook in Werkzeug: editing, undo/redo, bundle download, document import/export, failed-import preservation and restart passed')
finally:
    stop()
