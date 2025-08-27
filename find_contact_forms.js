const fs = require('fs');
const path = require('path');
const { parse } = require('fast-csv');
const puppeteer = require('puppeteer');

/** ============ CONFIG ============ */
const INPUT_CSV  = path.resolve('results.csv');          // input file
const OUTPUT_CSV = path.resolve('contact_forms.csv'); // output file
const HEADLESS   = false;                             // set true for headless
const NAV_TIMEOUT = 60000;
const WAIT_AFTER_NAV_MS = 1200;
const KEYWORDS = ['contact', 'about', 'feedback', 'support', 'help'];
const SAVE_ONLY_FORMS = true; // only rows with "Form found"

/** ============ UTILS ============ */
function normalizeUrl(u) {
  if (!u) return null;
  const s = String(u).trim();
  if (!s) return null;
  return /^https?:\/\//i.test(s) ? s : `https://${s}`;
}

async function readUrlsFromCsv(csvPath) {
  if (!fs.existsSync(csvPath)) {
    throw new Error(`Input CSV not found at ${csvPath}`);
  }
  return new Promise((resolve, reject) => {
    const urls = [];
    let hasHeader = false;

    fs.createReadStream(csvPath)
      .pipe(parse({ headers: true }))
      .on('error', reject)
      .on('headers', headers => {
        hasHeader = headers.map(h => h.toLowerCase()).includes('url');
      })
      .on('data', row => {
        const raw = hasHeader ? row.url : Object.values(row)[0];
        const u = normalizeUrl(raw);
        if (u) urls.push(u);
      })
      .on('end', () => resolve([...new Set(urls)]));
  });
}

// Basic heuristic: page has a <form> containing fields for name, phone, email, message
async function pageHasDesiredForm(page) {
  // Give SPA pages a moment to render
  await page.waitForTimeout(WAIT_AFTER_NAV_MS);

  // If there are zero forms, quick exit
  const formCount = await page.$$eval('form', forms => forms.length).catch(() => 0);
  if (formCount === 0) return false;

  // Check each form for required fields
  return await page.evaluate(() => {
    const forms = Array.from(document.querySelectorAll('form'));

    const hasNameField = (form) =>
      form.querySelector('input[name*="name" i], input[id*="name" i], input[placeholder*="name" i]');

    const hasPhoneField = (form) =>
      form.querySelector(
        'input[type="tel"], input[name*="phone" i], input[id*="phone" i], input[placeholder*="phone" i], input[name*="mobile" i]'
      );

    const hasEmailField = (form) =>
      form.querySelector(
        'input[type="email"], input[name="email" i], input[id="email" i], input[placeholder*="email" i]'
      );

    const hasMessageField = (form) =>
      form.querySelector(
        'textarea, textarea[name*="message" i], textarea[id*="message" i], textarea[placeholder*="message" i], input[name*="message" i]'
      ) ||
      // some sites use "comment", "enquiry", "enquiry"
      form.querySelector(
        'textarea[name*="comment" i], textarea[name*="enquiry" i], textarea[name*="enquiry" i]'
      );

    return forms.some((f) => hasNameField(f) && hasPhoneField(f) && hasEmailField(f) && hasMessageField(f));
  });
}

async function getCandidateLinks(page) {
  // Collect anchors (navbar, footer, anywhere) and filter by KEYWORDS in text OR URL
  const anchors = await page.$$eval('a', as =>
    as.map(a => ({
      text: (a.innerText || '').trim(),
      href: a.getAttribute('href') || ''
    }))
  );

  const base = new URL(page.url());
  const out = [];
  for (const { text, href } of anchors) {
    if (!href) continue;
    const lowerText = text.toLowerCase();
    const lowerHref = href.toLowerCase();

    const matches =
      // match by visible text
      KEYWORDS.some(k => lowerText.includes(k)) ||
      // or path/query contains keywords (e.g., /contact, ?page=contact)
      KEYWORDS.some(k => lowerHref.includes(`/${k}`) || lowerHref.includes(`=${k}`) || lowerHref.includes(`#${k}`));

    if (!matches) continue;

    // resolve relative links
    let abs;
    try { abs = new URL(href, base).toString(); } catch { continue; }

    out.push({ text: text || '(no text)', url: abs });
  }

  // de-duplicate by URL
  const seen = new Set();
  return out.filter(x => (seen.has(x.url) ? false : (seen.add(x.url), true)));
}

/** CSV writer that appends rows and optionally filters to "Form found" only */
function makeCsvAppender(outputPath, saveOnlyForms) {
  const stream = fs.createWriteStream(outputPath, { encoding: 'utf8' });
  stream.write('main_url,link_text,checked_url,status\n');

  const q = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;

  return {
    write(row) {
      if (saveOnlyForms && row.status !== 'Form found') return;
      stream.write([q(row.main_url), q(row.link_text), q(row.checked_url), q(row.status)].join(',') + '\n');
    },
    end() { stream.end(); }
  };
}

/** ============ MAIN ============ */
(async () => {
  // Prepare output writer
  const csv = makeCsvAppender(OUTPUT_CSV, SAVE_ONLY_FORMS);

  // Launch browser
  const browser = await puppeteer.launch({
    headless: HEADLESS,
    defaultViewport: null,
    args: [
      '--no-sandbox',
      '--disable-dev-shm-usage'
    ]
  });

  try {
    const urls = await readUrlsFromCsv(INPUT_CSV);
    console.log(`Loaded ${urls.length} URL(s).`);

    for (const mainUrl of urls) {
      console.log(`\n🔎 Checking: ${mainUrl}`);
      const page = await browser.newPage();

      // Set a realistic UA + language
      await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118 Safari/537.36');
      await page.setExtraHTTPHeaders({ 'Accept-Language': 'en-US,en;q=0.9' });

      try {
        await page.goto(mainUrl, { waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT });

        // 1) Check main page itself
        if (await pageHasDesiredForm(page)) {
          csv.write({ main_url: mainUrl, link_text: '(main)', checked_url: mainUrl, status: 'Form found' });
          console.log('  ✅ Form found on main page');
        }

        // 2) Gather candidate links and check each
        const candidates = await getCandidateLinks(page);
        console.log(`  Found ${candidates.length} candidate link(s).`);

        for (const { text, url } of candidates) {
          try {
            await page.goto(url, { waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT });
            const ok = await pageHasDesiredForm(page);
            csv.write({ main_url: mainUrl, link_text: text, checked_url: url, status: ok ? 'Form found' : 'No form' });
            console.log(`   - ${ok ? '✅' : '❌'} ${text} -> ${url}`);
          } catch (err) {
            csv.write({ main_url: mainUrl, link_text: text, checked_url: url, status: `Error: ${String(err).slice(0,120)}` });
            console.log(`   - ⚠️ Error on ${url}: ${err.message || err}`);
          }
        }
      } catch (err) {
        csv.write({ main_url: mainUrl, link_text: '', checked_url: '', status: `Main page error: ${String(err).slice(0,120)}` });
        console.log(`  ⚠️ Main page error: ${err.message || err}`);
      } finally {
        await page.close();
      }
    }

    console.log(`\n✅ Done. Results saved to ${OUTPUT_CSV}`);
  } catch (err) {
    console.error('Fatal:', err);
  } finally {
    csv.end();
    await browser.close();
  }
})();
