const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const page = fs.readFileSync('src/dementia_care_robot/web.py', 'utf8');
const headStateScript = page.match(/const face=document\.getElementById\('face'\)[\s\S]*?\npoll\(\);/)[0];
const emotionScript = fs.readFileSync('src/dementia_care_robot/static/site/head-emotions.js', 'utf8');

test('emotion changes play once; unchanged polls and calm stay silent', async () => {
  const face = {style:{}, setAttribute() {}};
  const label = {};
  const buttons = {happyDemo:{}, sadDemo:{}};
  const states = [
    {sequence:0, state:'idle', emotion:'calm'},
    {sequence:1, state:'speaking', emotion:'happy'},
    {sequence:1, state:'speaking', emotion:'happy'},
    {sequence:2, state:'sad', emotion:'sad'},
    {sequence:3, state:'idle', emotion:'calm'},
  ];
  const timers = new Map();
  const played = [];
  let nextTimer = 0;
  class AudioContext {
    constructor() { this.currentTime = 0; this.destination = {}; this.state = 'running'; }
    createOscillator() {
      const oscillator = {frequency:{}, connect:() => ({connect() {}}), start() {}, stop() {}};
      Object.defineProperty(oscillator.frequency, 'value', {set: value => played.push(value)});
      return oscillator;
    }
    createGain() { return {gain:{setValueAtTime() {}, linearRampToValueAtTime() {}, exponentialRampToValueAtTime() {}}}; }
    close() {}
  }
  const context = {
    document:{getElementById: id => ({face, label, ...buttons})[id]},
    window:{AudioContext},
    fetch:async () => ({json:async () => states.shift()}),
    setTimeout:(fn, delay) => { const id = ++nextTimer; timers.set(id, {fn, delay}); return id; },
    clearTimeout:id => timers.delete(id),
    addEventListener() {},
  };
  buttons.happyDemo.addEventListener = (_, handler) => { buttons.happyDemo.click = handler; };
  buttons.sadDemo.addEventListener = (_, handler) => { buttons.sadDemo.click = handler; };
  vm.runInNewContext(headStateScript, context);
  vm.runInNewContext(emotionScript, context);

  const pollAgain = async () => {
    const entry = [...timers].find(([, timer]) => timer.delay === 250);
    assert.ok(entry);
    timers.delete(entry[0]);
    await entry[1].fn();
  };
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(played.length, 0);
  await pollAgain();
  assert.equal(face.className, 'face speaking emotion-happy');
  assert.deepEqual(played, [523, 659, 784]);
  await pollAgain();
  assert.equal(played.length, 3);
  await pollAgain();
  assert.equal(face.className, 'face sad emotion-sad');
  assert.deepEqual(played.slice(3), [392, 349, 294]);
  await pollAgain();
  assert.equal(played.length, 6);
  assert.equal(face.className, 'face idle emotion-calm');
});
