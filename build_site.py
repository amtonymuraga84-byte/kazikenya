"""
build_site.py: builds the indexable parts of KaziKE from jobs.json.
Creates: jobs/<slug>.html (with Google JobPosting data), guides/, about/contact/privacy/terms pages,
style.css, sitemap.xml, robots.txt, and refreshes the nav/footer/head inside index.html.
Run after job_aggregator.py (the GitHub Action does both).
"""
import html
import json
import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

# ===== EDIT THESE =====
SITE_URL = "https://kazikenya.amtonymuraga84.workers.dev"  # change to your own domain, no trailing slash
CONTACT_EMAIL = "hello@example.co.ke"                      # a real inbox you read
WHATSAPP_URL = ""      # e.g. https://whatsapp.com/channel/XXXX   (leave empty to hide)
TELEGRAM_URL = ""      # e.g. https://t.me/yourchannel            (leave empty to hide)
CF_BEACON_TOKEN = ""   # Cloudflare > Web Analytics > your site > token (leave empty to disable)
# ======================

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
FAV = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E"
       "%3Ctext y='.9em' font-size='90'%3E💼%3C/text%3E%3C/svg%3E")
AD = '<div class="ad">Advertisement<br>{}</div>'
EMP = {"Full-time": "FULL_TIME", "Part-time": "PART_TIME", "Contract": "CONTRACTOR", "Internship": "INTERN"}


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def head_extra(path="/"):
    beacon = (f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
              f'data-cf-beacon=\'{{"token": "{E(CF_BEACON_TOKEN)}"}}\'></script>') if CF_BEACON_TOKEN else ""
    font = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;700;800&display=swap">')
    return (f'{font}<link rel="canonical" href="{SITE_URL}{path}"><link rel="icon" href="{FAV}">'
            f'<meta property="og:site_name" content="KaziKE"><meta property="og:type" content="website">'
            f'<meta property="og:url" content="{SITE_URL}{path}"><meta name="twitter:card" content="summary">{beacon}')


NAV = '<a href="/#jobs">Jobs</a><a href="/guides/">Guides</a><a href="/about.html">About</a><a href="/contact.html">Contact</a>'
HEADER = f'<header><div class="w"><a class="logo" href="/">Kazi<b>KE</b></a><nav>{NAV}</nav></div></header>'


def alerts_box():
    btns = ""
    if WHATSAPP_URL:
        btns += f'<a class="btn" href="{E(WHATSAPP_URL)}" rel="noopener">WhatsApp</a>'
    if TELEGRAM_URL:
        btns += f'<a class="btn o" href="{E(TELEGRAM_URL)}" rel="noopener">Telegram</a>'
    if not btns:
        return ""
    return f'<div class="alerts"><span><b>🔔 Get new jobs on your phone</b><br><span class="meta">Free daily job alerts</span></span><span class="row">{btns}</span></div>'


def footer():
    btns = ""
    if WHATSAPP_URL:
        btns += f'<a class="btn" href="{E(WHATSAPP_URL)}" rel="noopener">Job alerts on WhatsApp</a> '
    if TELEGRAM_URL:
        btns += f'<a class="btn o" href="{E(TELEGRAM_URL)}" rel="noopener">Telegram channel</a>'
    alerts = f'<p>{btns}</p>' if btns else ""
    return (f'<footer><div class="w">{alerts}<p><a href="/about.html">About</a> · <a href="/contact.html">Contact</a> · '
            f'<a href="/privacy.html">Privacy</a> · <a href="/terms.html">Terms</a> · <a href="/guides/">Guides</a></p>'
            f'<p>© {date.today().year} KaziKE. Listings come from public feeds and are checked automatically, so details '
            f'can be wrong or out of date. Verify the employer, and never pay to get a job. '
            f'<a href="mailto:{E(CONTACT_EMAIL)}">Report a scam</a></p></div></footer>')


def page(title, desc, path, body, extra=""):
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            f'<title>{E(title)}</title><meta name="description" content="{E(desc)}">'
            f'<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">'
            f'{head_extra(path)}<link rel="stylesheet" href="/style.css">{extra}</head><body>{HEADER}'
            f'<main><div class="w prose">{body}</div></main>{footer()}</body></html>')


def write(path, text):
    p = Path(path.lstrip("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


# ---------- job pages ----------
def job_page(j, all_jobs):
    path = f"/jobs/{j['slug']}.html"
    posted = j["posted"]
    valid = j.get("deadline") or (datetime.fromisoformat(posted) + timedelta(days=30)).date().isoformat()
    remote = j["l"] == "Remote"
    ld = {"@context": "https://schema.org", "@type": "JobPosting", "title": j["t"], "description": j["x"],
          "datePosted": posted, "validThrough": valid, "employmentType": EMP.get(j["y"], "OTHER"),
          "hiringOrganization": {"@type": "Organization", "name": j["c"]}, "directApply": False,
          "url": SITE_URL + path, "identifier": {"@type": "PropertyValue", "name": j.get("src", "KaziKE"), "value": j["id"]}}
    if remote:
        ld["jobLocationType"] = "TELECOMMUTE"
        ld["applicantLocationRequirements"] = {"@type": "Country", "name": "Kenya"}
    else:
        ld["jobLocation"] = {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": j["l"],
                                                           "addressCountry": "KE"}}
    rel = [r for r in all_jobs if r["k"] == j["k"] and r["id"] != j["id"]][:4]
    relh = "".join(f'<li><a href="/jobs/{r["slug"]}.html">{E(r["t"])}</a> · {E(r["c"])} · {E(r["l"])}</li>' for r in rel)
    body = (f'<p class="crumbs"><a href="/">Jobs</a> › {E(j["k"])}</p><h1>{E(j["t"])}</h1>'
            f'<p class="meta">{E(j["c"])} · {E(j["l"])} · Posted {E(posted)}'
            f'{" · Closes " + E(j["deadline"]) if j.get("deadline") else ""}</p>'
            f'<p><span class="tag">{E(j["y"])}</span><span class="tag">{E(j["k"])}</span>'
            f'{"<span class=tag>" + E(j["p"]) + "</span>" if j.get("p") else ""}</p>'
            f'{AD.format("Top banner")}<h2>About the role</h2><p>{E(j["x"])}</p>'
            f'<p><a class="btn" href="{E(j["u"])}" target="_blank" rel="nofollow noopener">Apply on the original page</a></p>'
            f'<p class="meta">Source: {E(j.get("src", "Direct"))}. We link to the original listing; confirm every detail there. '
            f'Never pay a fee to get a job or interview. '
            f'<a href="mailto:{E(CONTACT_EMAIL)}?subject=Report%20job%3A%20{E(j["id"])}">Report this job</a></p>'
            f'{alerts_box()}{AD.format("In-content 300×250 / responsive")}'
            + (f'<h2>More {E(j["k"])} jobs</h2><ul>{relh}</ul>' if rel else "")
            + '<p><a href="/#jobs">← Back to all jobs</a></p>')
    write(path, page(f'{j["t"]} at {j["c"]} ({j["l"]}) | KaziKE', j["x"][:155], path, body,
                     f'<script type="application/ld+json">{json.dumps(ld).replace("</", "<\\/")}</script>'))


# ---------- guides & legal ----------
GUIDES = {
    "cv-tips-kenya": ("How to Write a CV That Gets Shortlisted in Kenya",
        "Practical CV tips for Kenyan job seekers: structure, keywords, length and common mistakes.",
        "<p>Recruiters in Kenya often review dozens of CVs for a single role, and many companies now filter them with "
        "applicant tracking software first. A clear, honest CV gives you the best chance of being read.</p>"
        "<h2>Keep it to two pages</h2><p>Lead with a three-line professional summary, then your most recent role. "
        "Early-career applicants can fit everything on one page. Cut anything older than ten years unless it is directly relevant.</p>"
        "<h2>Show results, not duties</h2><p>Instead of “handled customer queries”, write what changed: “resolved 40+ queries a day "
        "with a 95% satisfaction score”. Only use numbers you can defend in an interview.</p>"
        "<h2>Match the advert</h2><p>Read the vacancy and reuse its key terms where they truthfully describe you. "
        "Use plain headings (Experience, Education, Skills) and avoid tables, text boxes and photos that software can’t read.</p>"
        "<h2>Check the details</h2><ul><li>One professional email address and a working phone number</li>"
        "<li>No spelling errors; ask someone to proofread</li><li>Save as PDF unless the employer asks for Word</li>"
        "<li>Name the file clearly, for example <i>Jane-Wanjiku-CV.pdf</i></li></ul>"),
    "spot-fake-jobs-kenya": ("How to Spot a Fake Job Advert in Kenya",
        "Warning signs of job scams in Kenya and what to do if you suspect one.",
        "<p>Job scams target people who are searching hard for work. Knowing the warning signs protects your money and your personal data.</p>"
        "<h2>Red flags</h2><ul><li><b>You are asked to pay.</b> Real employers do not charge for interviews, uniforms, training or “processing”.</li>"
        "<li><b>Contact is only by personal email or WhatsApp</b> with no company website or office address.</li>"
        "<li><b>The pay is unrealistic</b> for the work, or the job needs no skills or interview.</li>"
        "<li><b>You are rushed</b> to decide or send money today.</li>"
        "<li><b>They ask for sensitive documents early</b>, such as ID copies, bank PINs or M-Pesa PINs.</li></ul>"
        "<h2>Check before you apply</h2><p>Search the company name, look for an official website and social pages, and find the "
        "vacancy on the employer’s own careers page. Call the office using a number you found yourself.</p>"
        "<h2>If you suspect a scam</h2><p>Stop contact and do not send money. Report it to the platform that showed the advert, "
        "and to the police or the Communications Authority if you lost money. You can also report any listing on KaziKE using the link on its page.</p>"),
    "interview-tips-kenya": ("Interview Preparation: 10 Questions to Practise",
        "A simple preparation routine and common interview questions for job seekers in Kenya.",
        "<p>Good preparation matters more than natural confidence. Spend an hour on the steps below before any interview.</p>"
        "<h2>Before the day</h2><ul><li>Read the vacancy and list how your experience matches each requirement</li>"
        "<li>Learn what the organisation does, its products or programmes, and recent news</li>"
        "<li>Plan your route and arrive early, or test your video call and internet for online interviews</li></ul>"
        "<h2>Questions to practise</h2><ol><li>Tell me about yourself.</li><li>Why do you want this job?</li>"
        "<li>Why should we hire you?</li><li>What is your greatest strength?</li><li>What is a weakness you are working on?</li>"
        "<li>Describe a problem you solved at work or school.</li><li>Tell me about a time you worked in a team.</li>"
        "<li>How do you handle pressure and deadlines?</li><li>Where do you see yourself in five years?</li>"
        "<li>What are your salary expectations?</li></ol>"
        "<h2>Answer with a story</h2><p>For behavioural questions, describe the situation, what you did, and the result. "
        "Finish by asking one or two thoughtful questions about the role.</p>"),
}


def static_pages():
    for slug, (t, d, b) in GUIDES.items():
        write(f"/guides/{slug}.html", page(f"{t} | KaziKE", d, f"/guides/{slug}.html",
                                           f"<h1>{E(t)}</h1>{b}{AD.format('In-content ad')}<p><a href='/guides/'>← All guides</a></p>"))
    items = "".join(f'<li><a href="/guides/{s}.html"><b>{E(t)}</b></a><br><span class="meta">{E(d)}</span></li>'
                    for s, (t, d, _) in GUIDES.items())
    write("/guides/index.html", page("Career Guides | KaziKE", "CV, interview and job-scam guides for Kenyan job seekers.",
                                     "/guides/", f"<h1>Career guides</h1><ul>{items}</ul>"))
    write("/about.html", page("About KaziKE", "KaziKE lists jobs in Kenya and remote roles open to Kenyans.", "/about.html",
        "<h1>About KaziKE</h1><p>KaziKE helps people in Kenya find jobs in Nairobi, Mombasa, Kisumu and beyond, plus remote roles "
        "open to applicants in Kenya. Browsing is free.</p><h2>How listings are collected</h2>"
        "<p>We gather vacancies from public job feeds and partner sources. Software summarises each listing in plain language, "
        "keeps only jobs relevant to Kenya, and flags adverts that look like scams. Every listing links to the original page, "
        "where you apply. Summaries can contain mistakes, so always check the original advert.</p>"
        "<h2>How we make money</h2><p>The site shows advertising and may carry sponsored listings, which are labelled. "
        "We never charge job seekers.</p>"
        f'<h2>Contact</h2><p><a href="mailto:{E(CONTACT_EMAIL)}">{E(CONTACT_EMAIL)}</a></p>'))
    write("/contact.html", page("Contact KaziKE", "Contact KaziKE to report a job, an error or to advertise.", "/contact.html",
        f'<h1>Contact us</h1><p>Email <a href="mailto:{E(CONTACT_EMAIL)}">{E(CONTACT_EMAIL)}</a>.</p>'
        "<ul><li><b>Report a scam or expired job:</b> include the page link.</li>"
        "<li><b>Employers:</b> ask about featured listings and advertising.</li>"
        "<li><b>Remove a listing:</b> tell us the link and we will take it down.</li></ul>"))
    write("/privacy.html", page("Privacy Policy | KaziKE", "How KaziKE handles visitor data, cookies and advertising.", "/privacy.html",
        f"<h1>Privacy Policy</h1><p class='meta'>Last updated {date.today().isoformat()}</p>"
        "<p>This policy explains what information KaziKE collects and how it is used, in line with the Kenya Data Protection Act, 2019.</p>"
        "<h2>What we collect</h2><p>We do not ask visitors to create accounts. We collect basic, aggregated visit data "
        "(pages viewed, device type, approximate location) through privacy-friendly analytics. If you email us, we keep your message and address to reply.</p>"
        "<h2>Cookies and advertising</h2><p>Third parties, including Google, may show ads on this site and use cookies to serve ads based on your "
        "visits here and to other sites. You can manage personalised ads at <a href='https://adssettings.google.com'>adssettings.google.com</a> "
        "or learn more at <a href='https://www.aboutads.info'>aboutads.info</a>.</p>"
        "<h2>Links to other sites</h2><p>Job listings link to external employer or job-board pages with their own privacy practices. "
        "Do not share sensitive details until you have verified the employer.</p>"
        "<h2>Your rights</h2><p>You may ask what data we hold about you, and request correction or deletion, by emailing "
        f"<a href='mailto:{E(CONTACT_EMAIL)}'>{E(CONTACT_EMAIL)}</a>.</p>"))
    write("/terms.html", page("Terms of Use | KaziKE", "Terms for using KaziKE.", "/terms.html",
        f"<h1>Terms of Use</h1><p class='meta'>Last updated {date.today().isoformat()}</p>"
        "<p>KaziKE is an information service. Listings come from third parties, we are not the employer, and we cannot guarantee "
        "that any job is genuine, available or accurate.</p><ul><li>Verify each employer before sharing personal information or applying.</li>"
        "<li>Never pay money to get a job or interview.</li><li>Sponsored listings and ads are labelled.</li>"
        "<li>We may remove any listing at any time.</li><li>To the extent allowed by law, KaziKE is not liable for losses arising from use of the site.</li></ul>"))


def patch(text, tag, content):
    return re.sub(rf"<!--{tag}-->.*?<!--/{tag}-->", lambda _: f"<!--{tag}-->{content}<!--/{tag}-->", text, flags=re.S)


def main():
    idx = Path("index.html").read_text(encoding="utf-8")
    css = re.search(r"<style>(.*?)</style>", idx, re.S).group(1)
    css += (".w.prose{max-width:780px;padding-block:24px}.prose h2{margin:22px 0 8px}.prose li{margin:5px 0}"
            ".crumbs{font-size:14px;color:var(--muted)}footer a{margin-right:4px}.alerts{display:flex;gap:12px;flex-wrap:wrap;align-items:center;justify-content:space-between;background:var(--soft);border:1px solid var(--bd);border-radius:12px;padding:12px 14px;margin:14px 0}.row{display:flex;gap:8px;flex-wrap:wrap}footer p{margin:8px 0}.prose{font-size:18px;line-height:1.65}.prose h1{font-size:clamp(28px,5vw,42px);line-height:1.15}")
    write("/style.css", css)

    jobs = [j for j in json.loads(Path("jobs.json").read_text(encoding="utf-8")) if j.get("src") != "Sample"]
    shutil.rmtree("jobs", ignore_errors=True)
    for j in jobs:
        j["slug"] = f"{slugify(j['t'] + '-' + j['c'])}-{j['id'][:6]}"
    for j in jobs:
        job_page(j, jobs)
    Path("jobs.json").write_text(json.dumps(jobs, ensure_ascii=False, indent=1), encoding="utf-8")
    static_pages()

    today = date.today().isoformat()
    urls = ["/", "/guides/", "/about.html", "/contact.html", "/privacy.html", "/terms.html"]
    urls += [f"/guides/{s}.html" for s in GUIDES] + [f"/jobs/{j['slug']}.html" for j in jobs]
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{SITE_URL}{u}</loc><lastmod>{today}</lastmod></url>" for u in urls) + "</urlset>")
    write("/robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")

    for tag, content in (("NAV", NAV), ("HEAD", head_extra("/")), ("ALERTS", alerts_box()), ("FOOT", footer())):
        idx = patch(idx, tag, content)
    Path("index.html").write_text(idx, encoding="utf-8")
    print(f"Built {len(jobs)} job pages, {len(urls)} URLs in sitemap")


if __name__ == "__main__":
    main()
