const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/dementia_care_robot/static/site/wake-voice.js', 'utf8');
const {fredWakeCommand} = require('../src/dementia_care_robot/static/site/wake-voice.js');

test('wake name is a word, and only following text becomes the request', () => {
  assert.equal(fredWakeCommand('unrelated private speech'), null);
  assert.equal(fredWakeCommand('Alfred is here'), null);
  assert.equal(fredWakeCommand('Hey FRED, how are you?'), 'how are you?');
  assert.equal(fredWakeCommand('Fred'), '');
});

function harness() {
  const toggle = {}, status = {}, manual = {textContent:'Start speaking', disabled:false, before() {}};
  const button = {}, input = {}, chat = {querySelector() {}, append() {}};
  const form = {querySelector: () => button, querySelectorAll: () => [button,input]};
  const panel = {querySelector: s => s === 'button' ? toggle : status};
  const elements = {talkButton:manual, messageForm:form, chat};
  const timers = new Map(), recognizers = [], requests = []; let id = 0;
  class Recognition {
    constructor() { recognizers.push(this); }
    start() {} abort() { this.aborted = true; }
    result(text) { this.onresult({resultIndex:0, results:[Object.assign([{transcript:text}], {isFinal:true})]}); }
  }
  const context = {
    document:{getElementById: id => elements[id], createElement: tag => tag === 'section' ? panel : {}, addEventListener() {}},
    window:{SpeechRecognition:Recognition, speechSynthesis:{cancel() {}, speak(u) { context.utterance=u; }}},
    navigator:{language:'en-US'}, addEventListener() {}, SpeechSynthesisUtterance:class {constructor(text){this.text=text;}},
    setTimeout:(fn,ms) => {timers.set(++id,{fn,ms});return id;}, clearTimeout:id => timers.delete(id),
    AbortController, fetch:async (url, options) => {requests.push({url,options});return {ok:true,json:async()=>({reply:'Hello'})};},
  };
  vm.runInNewContext(source,context);
  return {context,toggle,status,recognizers,requests, async timer(ms) {
    const entry=[...timers].find(([,t])=>t.ms===ms); assert.ok(entry,`timer ${ms}`);
    timers.delete(entry[0]); await entry[1].fn();
  }};
}
test('ignores ambient speech, accepts wake then question, pauses until TTS ends', async () => {
  const h=harness(); h.toggle.onclick(); const r=h.recognizers[0];
  r.result('ordinary conversation');
  assert.equal(h.requests.length,0);
  r.result('Hey Fred'); r.result('How are you?'); await h.timer(1400);
  const turns=h.requests.filter(r=>r.url==='/api/conversation');
  assert.equal(turns.length,1); assert.equal(JSON.parse(turns[0].options.body).message,'How are you?');
  assert.ok(r.aborted); assert.equal(h.recognizers.length,1);
  h.context.utterance.onend(); await h.timer(700); assert.equal(h.recognizers.length,2);
  h.toggle.onclick(); assert.ok(h.recognizers[1].aborted);
});
test('wake with no question expires without sending a conversation', async () => {
  const h=harness(); h.toggle.onclick(); h.recognizers[0].result('Fred');
  await h.timer(15000);
  assert.equal(h.requests.filter(r=>r.url==='/api/conversation').length,0);
});
