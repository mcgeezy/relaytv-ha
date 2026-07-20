#!/usr/bin/env node
// SPDX-License-Identifier: GPL-3.0-only

/*
 * Capture and compose the README product images for the RelayTV Home Assistant
 * integration. Screenshots are taken from a live Home Assistant instance that
 * already has RelayTV set up and playing something (so the media card is rich),
 * then framed in browser/phone chrome for the README and release/ad assets.
 *
 * Auth: pass a Home Assistant long-lived (or short-lived) access token via the
 * HA_TOKEN environment variable. The token is injected into the frontend's
 * localStorage so the capture runs as that user; it is never written to disk.
 *
 * Example:
 *   HA_TOKEN=xxxxx node scripts/readme-screenshots.mjs \
 *     --ws=ws://127.0.0.1:3000/ \
 *     --ha=http://homeassistant.local:8123 \
 *     --device=<relaytv_device_id> \
 *     --entity=media_player.living_room_tv \
 *     --output=docs/images/readme
 */

import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

function option(name, fallback) {
  const prefix = `--${name}=`;
  const found = process.argv.find((arg) => arg.startsWith(prefix));
  return found ? found.slice(prefix.length) : fallback;
}

const WS = option('ws', 'ws://127.0.0.1:3000/');
const HA = option('ha', 'http://homeassistant.local:8123').replace(/\/$/, '');
const DEVICE_ID = option('device', '');
const ENTITY = option('entity', 'media_player.living_room_tv');
const PANEL = option('panel', 'relaytv');
const OUTPUT = path.resolve(option('output', 'docs/images/readme'));
const LOGO = path.resolve(option('logo', 'logo.png'));
const TOKEN = process.env.HA_TOKEN;
const REFRESH = process.env.HA_REFRESH || '';

if (!TOKEN) {
  process.stderr.write('HA_TOKEN environment variable is required.\n');
  process.exit(2);
}
fs.mkdirSync(OUTPUT, { recursive: true });

const tokens = {
  hassUrl: HA,
  clientId: `${HA}/`,
  access_token: TOKEN,
  refresh_token: REFRESH,
  token_type: 'Bearer',
  expires_in: 1800,
  ha_auth_provider: 'homeassistant',
  expires: Date.now() + 1800 * 1000,
};

const uri = (buffer) => `data:image/png;base64,${buffer.toString('base64')}`;

async function newContext(browser, viewport) {
  const ctx = await browser.newContext({ viewport, colorScheme: 'dark', deviceScaleFactor: 2 });
  await ctx.addInitScript((t) => {
    try { localStorage.setItem('hassTokens', JSON.stringify(t)); } catch (_e) {}
    try { localStorage.setItem('selectedTheme', JSON.stringify({ dark: true })); } catch (_e) {}
  }, tokens);
  return ctx;
}

async function waitApp(page) {
  await page.waitForFunction(() => !!document.querySelector('home-assistant'), { timeout: 20000 });
  await page.waitForTimeout(2500);
}

async function captureMoreInfo(browser) {
  const ctx = await newContext(browser, { width: 460, height: 940 });
  const page = await ctx.newPage();
  await page.goto(`${HA}/lovelace/0`, { waitUntil: 'domcontentloaded' }).catch(() => {});
  await waitApp(page);
  await page.evaluate((entityId) => {
    document.querySelector('home-assistant').dispatchEvent(
      new CustomEvent('hass-more-info', { detail: { entityId }, bubbles: true, composed: true }));
  }, ENTITY);
  await page.waitForTimeout(2500);
  const buffer = await page.screenshot({ type: 'png' });
  await ctx.close();
  return buffer;
}

async function captureDesktop(browser, url, settle = 1500) {
  const ctx = await newContext(browser, { width: 1500, height: 950 });
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: 'domcontentloaded' }).catch(() => {});
  await waitApp(page);
  await page.waitForTimeout(settle);
  const buffer = await page.screenshot({ type: 'png' });
  await ctx.close();
  return buffer;
}

const FONT = "Inter,ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif";
const BG = `
  radial-gradient(circle at 78% 14%,rgba(65,189,245,.26),transparent 30%),
  radial-gradient(circle at 16% 88%,rgba(56,189,248,.22),transparent 36%),
  linear-gradient(150deg,#050b16,#08182b 55%,#060f1d)`;
const GRID = 'linear-gradient(rgba(255,255,255,.12) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.12) 1px,transparent 1px)';

const CSS = `
  *{box-sizing:border-box;margin:0} html,body{width:100%;height:100%;overflow:hidden}
  body{position:relative;font-family:${FONT};color:#eef6ff;background:${BG}}
  .grid{position:absolute;inset:0;opacity:.11;background-image:${GRID};background-size:54px 54px}
  .flare{position:absolute;border-radius:50%;filter:blur(80px)}
  .win{position:relative;border-radius:16px;overflow:hidden;background:#0b1420;
    border:1px solid rgba(150,200,255,.22);box-shadow:0 44px 96px rgba(0,0,0,.55),0 0 60px rgba(45,150,235,.12)}
  .bar{display:flex;align-items:center;gap:9px;height:44px;padding:0 16px;background:#111c2b;border-bottom:1px solid rgba(150,200,255,.14)}
  .dot{width:13px;height:13px;border-radius:50%}.dot.r{background:#ff5f57}.dot.y{background:#febc2e}.dot.g{background:#28c840}
  .addr{flex:1;margin-left:12px;height:26px;border-radius:8px;background:#0a1420;border:1px solid rgba(150,200,255,.16);
    color:#8fb2d6;font-size:13px;font-weight:600;display:flex;align-items:center;padding:0 14px}
  .winimg{display:block;width:100%}
  .phone{position:relative;padding:11px;border-radius:46px;background:#02060d;
    border:1px solid rgba(255,255,255,.26);box-shadow:0 40px 82px rgba(0,0,0,.62),0 0 0 5px rgba(65,189,245,.10)}
  .phoneimg{display:block;width:100%;border-radius:36px}
  .island{position:absolute;z-index:3;top:22px;left:50%;width:104px;height:26px;transform:translateX(-50%);border-radius:16px;background:#02060d}
  .brand{position:absolute;z-index:8;display:flex;align-items:center;gap:16px}
  .brand img{height:60px;filter:drop-shadow(0 10px 22px rgba(0,0,0,.4))}
  .hapill{display:inline-flex;align-items:center;gap:9px;padding:9px 16px;border-radius:999px;
    background:rgba(65,189,245,.12);border:1px solid rgba(65,189,245,.4);color:#bfe8ff;font-size:15px;font-weight:700}
  .hadot{width:11px;height:11px;border-radius:50%;background:#41BDF5;box-shadow:0 0 12px #41BDF5}
  .tagline{position:absolute;z-index:8;font-weight:760;letter-spacing:-.025em}
  .pills{display:flex;gap:11px;margin-top:16px}
  .pill{padding:9px 15px;border:1px solid rgba(131,213,255,.26);border-radius:999px;background:rgba(9,24,44,.72);
    color:#cdeeff;font-size:13px;font-weight:740;letter-spacing:.09em;text-transform:uppercase}
  .eyebrow{color:#65ddff;font-size:15px;font-weight:800;letter-spacing:.16em;text-transform:uppercase}
  .label{margin-top:9px;font-size:30px;font-weight:780;letter-spacing:-.03em}
  .sub{margin-top:12px;font-size:17px;line-height:1.5;color:#a9c6e0;max-width:88%}
  .copy{position:absolute;z-index:8}
`;

function browserFrame(img, url, w) {
  return `<div class="win" style="width:${w}px">
    <div class="bar"><span class="dot r"></span><span class="dot y"></span><span class="dot g"></span>
      <div class="addr">${url}</div></div>
    <img class="winimg" src="${img}" alt=""></div>`;
}

function phoneFrame(img, w) {
  return `<div class="phone" style="width:${w}px"><div class="island"></div>
    <img class="phoneimg" src="${img}" alt=""></div>`;
}

function heroHtml(panel, moreinfo, logo) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>${CSS}
    .flare.a{right:-40px;top:20px;width:600px;height:680px;background:rgba(65,189,245,.16)}
    .flare.b{left:-80px;bottom:-80px;width:540px;height:540px;background:rgba(56,189,248,.13)}
    .brand{left:64px;top:56px}
    .stage{position:absolute;z-index:4;left:64px;top:158px;width:1000px}
    .fphone{position:absolute;z-index:6;right:96px;top:224px;transform:rotate(3deg)}
    .tagline{left:70px;bottom:72px;font-size:40px;line-height:1.06;max-width:1000px}
    .tagline .thin{color:#a9c6e0;font-weight:600}
  </style></head><body>
    <div class="grid"></div><div class="flare a"></div><div class="flare b"></div>
    <div class="brand"><img src="${logo}" alt="RelayTV"><span class="hapill"><span class="hadot"></span>Works with Home Assistant</span></div>
    <div class="stage">${browserFrame(panel, 'homeassistant.local:8123 / relaytv', 1000)}</div>
    <div class="fphone">${phoneFrame(moreinfo, 316)}</div>
    <div class="tagline">Your TV. <span class="thin">Native in Home Assistant.</span>
      <div class="pills"><span class="pill">Control</span><span class="pill">Automate</span><span class="pill">Embed</span></div></div>
  </body></html>`;
}

function cardHtml({ img, kind, w, eyebrow, label, sub }) {
  const frame = kind === 'phone' ? phoneFrame(img, w) : browserFrame(img, 'homeassistant.local:8123', w);
  const place = kind === 'phone'
    ? '.frame{position:absolute;z-index:4;right:64px;top:50%;transform:translateY(-50%)}'
    : '.frame{position:absolute;z-index:4;right:56px;top:50%;transform:translateY(-50%)}';
  return `<!doctype html><html><head><meta charset="utf-8"><style>${CSS}
    .flare.a{right:120px;top:60px;width:520px;height:560px;background:rgba(65,189,245,.14)}
    ${place}
    .copy{left:52px;top:48px;max-width:${kind === 'phone' ? 620 : 560}px}
  </style></head><body>
    <div class="grid"></div><div class="flare a"></div>
    <div class="copy"><div class="eyebrow">${eyebrow}</div><div class="label">${label}</div><div class="sub">${sub}</div>
      <div class="pills"><span class="pill">Home Assistant</span></div></div>
    <div class="frame">${frame}</div>
  </body></html>`;
}

async function render(browser, html, out, viewport) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.setContent(html, { waitUntil: 'load' });
  await page.waitForTimeout(400);
  await page.screenshot({ path: out, type: 'png' });
  await ctx.close();
}

async function main() {
  const browser = await chromium.connect(WS);
  try {
    const moreinfo = uri(await captureMoreInfo(browser));
    const device = uri(await captureDesktop(browser, `${HA}/config/devices/device/${DEVICE_ID}`));
    const panel = uri(await captureDesktop(browser, `${HA}/${PANEL}`, 4000));
    const logo = uri(fs.readFileSync(LOGO));

    await render(browser, heroHtml(panel, moreinfo, logo), path.join(OUTPUT, 'hero.png'), { width: 1600, height: 1000 });
    await render(browser, cardHtml({
      img: moreinfo, kind: 'phone', w: 360,
      eyebrow: 'Control', label: 'Native media controls',
      sub: 'Play, pause, seek, set volume, and mute from any Home Assistant dashboard, the mobile app, or a voice assistant — with live artwork and progress.',
    }), path.join(OUTPUT, 'control-phone.png'), { width: 1500, height: 760 });
    await render(browser, cardHtml({
      img: device, kind: 'browser', w: 900,
      eyebrow: 'Automate', label: 'A first-class Home Assistant device',
      sub: 'RelayTV registers as a real device with a media_player entity and RelayTV-specific actions, ready for automations, scripts, and dashboards.',
    }), path.join(OUTPUT, 'device-desktop.png'), { width: 1600, height: 820 });
    await render(browser, cardHtml({
      img: panel, kind: 'browser', w: 900,
      eyebrow: 'Embed', label: 'Your RelayTV remote in the sidebar',
      sub: 'Pin the full RelayTV web UI as a Home Assistant panel so the remote, queue, and Jellyfin/Emby library live one click away.',
    }), path.join(OUTPUT, 'panel-desktop.png'), { width: 1600, height: 820 });

    process.stdout.write(`${JSON.stringify({
      ok: true, ha: HA, output: OUTPUT,
      files: ['hero.png', 'control-phone.png', 'device-desktop.png', 'panel-desktop.png'],
    }, null, 2)}\n`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`README screenshot generation failed: ${error.stack || error}\n`);
  process.exit(1);
});
