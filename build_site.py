"""
build_site.py: builds the indexable parts of RemoteKazi from jobs.json.
Creates: jobs/<slug>.html (with Google JobPosting data), guides/, about/contact/privacy/terms pages,
style.css, sitemap.xml, robots.txt, and refreshes the nav/footer/head inside index.html.
Run after job_aggregator.py (the GitHub Action does both).
"""
import html
from urllib.parse import quote
import json
import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

# ===== EDIT THESE =====
SITE_URL = "https://remotekazi.com"  # change to your own domain, no trailing slash
CONTACT_EMAIL = "hello@remotekazi.com"                      # a real inbox you read
WHATSAPP_URL = "https://whatsapp.com/channel/0029Vb9Ag48EFeXcKNbsZ137"
TELEGRAM_URL = ""      # e.g. https://t.me/yourchannel            (leave empty to hide)
CF_BEACON_TOKEN = ""   # Cloudflare > Web Analytics > your site > token (leave empty to disable)
# Careers pages shown in the "Featured employers" section. Plain links only (no scraping).
# Add more as ("Name", "https://careers-page-address", "short note"). Check each link opens before you publish.
FEATURED_EMPLOYERS = [
    ("Google", "https://www.google.com/about/careers/applications/", "Roles worldwide, including Africa and remote"),
    ("Microsoft", "https://careers.microsoft.com/", "Engineering, sales and support roles"),
    ("United Nations Careers", "https://careers.un.org/", "UN jobs, internships and consultancies"),
    ("ReliefWeb Jobs", "https://reliefweb.int/jobs", "NGO and humanitarian jobs, filter by Kenya"),
    ("Public Service Commission of Kenya", "https://www.publicservice.go.ke/", "Official notices for government jobs"),
]
MAX_AGE_DAYS = 14   # keep in step with job_aggregator.py
SHOW_AD_PLACEHOLDERS = False   # keep False until you paste real ad code into the ad boxes
ADSENSE_CLIENT = ""   # your AdSense publisher ID, e.g. "ca-pub-1234567890123456". Adds the AdSense code to every page and writes ads.txt
# Old addresses that should send visitors (and Google) to a newer page. Kept here because _redirects is rebuilt on every run.
EXTRA_REDIRECTS = [
]
# ======================

PAGES_UPDATED = "2026-10-26"   # change when you edit the guides or about/contact/privacy/terms text
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
FAV = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E"
       "%3Ctext y='.9em' font-size='90'%3E💼%3C/text%3E%3C/svg%3E")
AD = '<div class="ad">Advertisement<br>{}</div>'
EMP = {"Full-time": "FULL_TIME", "Part-time": "PART_TIME", "Contract": "CONTRACTOR", "Internship": "INTERN"}


def snip(text, n=155):
    """Shorten text for a meta description without cutting a word in half."""
    t = re.sub(r"\s+", " ", text or "").strip()
    if len(t) <= n:
        return t
    return t[:n].rsplit(" ", 1)[0].rstrip(",;:-–") + "…"


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def head_extra(path="/", image=None):
    img = image or f"{SITE_URL}/og-image.png"
    ads = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={E(ADSENSE_CLIENT)}" '
           f'crossorigin="anonymous"></script><meta name="google-adsense-account" content="{E(ADSENSE_CLIENT)}">') if ADSENSE_CLIENT else ""
    beacon = (f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
              f'data-cf-beacon=\'{{"token": "{E(CF_BEACON_TOKEN)}"}}\'></script>') if CF_BEACON_TOKEN else ""
    adcss = '' if SHOW_AD_PLACEHOLDERS else '<style>.ad,aside{display:none!important}.main{grid-template-columns:minmax(0,1fr)!important}</style>'
    font = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800&display=swap">')
    return (f'{adcss}{font}<link rel="canonical" href="{SITE_URL}{path}"><link rel="icon" href="{FAV}">'
            f'<meta property="og:site_name" content="RemoteKazi"><meta property="og:type" content="website">'
            f'<meta property="og:url" content="{SITE_URL}{path}"><meta property="og:image" content="{img}">'
            f'<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
            f'<meta property="og:image:alt" content="RemoteKazi – jobs in Kenya and remote roles">'
            f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{img}">{beacon}{ads}')


_cta = TELEGRAM_URL or WHATSAPP_URL
NAV = '<a href="/#jobs">Jobs</a><a href="/blog/">Blog</a>' + (f'<a class="cta" href="{E(_cta)}" rel="noopener">Job alerts</a>' if _cta else "")
HEADER = f'<header><div class="w"><a class="logo" href="/">Remote<b>Kazi</b></a><nav>{NAV}</nav></div></header>'


def alerts_box():
    btns = ""
    if WHATSAPP_URL:
        btns += f'<a class="btn" href="{E(WHATSAPP_URL)}" rel="noopener">WhatsApp</a>'
    if TELEGRAM_URL:
        btns += f'<a class="btn o" href="{E(TELEGRAM_URL)}" rel="noopener">Telegram</a>'
    if not btns:
        return ""
    btns += ' <a class="btn o" href="https://www.google.com/alerts?q=site%3Aremotekazi.com%2Fjobs" target="_blank" rel="noopener">Google Alert</a>'
    return f'<div class="alerts"><span><b>🔔 Get new jobs on your phone</b><br><span class="meta">Free daily job alerts</span></span><span class="row">{btns}</span></div>'


def footer():
    btns = ""
    if WHATSAPP_URL:
        btns += f'<a class="btn" href="{E(WHATSAPP_URL)}" rel="noopener">Job alerts on WhatsApp</a> '
    if TELEGRAM_URL:
        btns += f'<a class="btn o" href="{E(TELEGRAM_URL)}" rel="noopener">Telegram channel</a>'
    btns += (' <a class="btn o" href="https://www.google.com/alerts?q=site%3Aremotekazi.com%2Fjobs" target="_blank" rel="noopener">Google Alert</a>'
             ' <a class="btn o" href="/jobs.xml">Jobs RSS</a>')
    alerts = f'<p>{btns}</p>' if btns else ""
    return (f'<footer><div class="w">{alerts}<p><a href="/about/">About</a> · <a href="/contact/">Contact</a> · '
            f'<a href="/privacy/">Privacy</a> · <a href="/terms/">Terms</a> · <a href="/guides/">Guides</a> · <a href="/blog/">Blog</a></p>'
            f'<p>© {date.today().year} RemoteKazi. Listings come from public feeds and are checked automatically, so details '
            f'can be wrong or out of date. Verify the employer, and never pay to get a job. '
            f'<a href="mailto:{E(CONTACT_EMAIL)}">Report a scam</a></p></div></footer>')


def page(title, desc, path, body, extra="", image=None):
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            f'<title>{E(title)}</title><meta name="description" content="{E(desc)}">'
            f'<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">'
            f'{head_extra(path, image)}<link rel="stylesheet" href="/style.css">{extra}</head><body>{HEADER}'
            f'<main><div class="w prose">{body}</div></main>{footer()}</body></html>')


def write(path, text):
    p = Path(path.lstrip("/"))
    if path.endswith("/"):
        p = p / "index.html"                      # clean URL: /about/ is served from about/index.html
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def featured_html():
    cards = "".join(
        f'<a class="card post" href="{E(u)}" target="_blank" rel="noopener"><b>{E(n)}</b>'
        f'<p class="meta">{E(d)}</p><span class="meta">Visit careers page →</span></a>'
        for n, u, d in FEATURED_EMPLOYERS)
    return cards


def tag_y(j):
    return f'<span class="tag">{E(j["y"])}</span>' if j["y"] != "Not stated" else ""


def card_html(j):
    d = (date.today() - datetime.fromisoformat(j["posted"]).date()).days
    when = "today" if d <= 0 else "1 day ago" if d == 1 else f"{d} days ago"
    pay = f'<span class="tag">{E(j["p"])}</span>' if j.get("p") else ""
    return (f'<article class="job{" f" if j.get("f") else ""}"><h3><a href="/jobs/{j["slug"]}/">{E(j["t"])}</a></h3>'
            f'<div class="meta">{E(j["c"])} · {E(j["l"])} · {when}</div>{tag_y(j)}<span class="tag">{E(j["k"])}</span>{pay}'
            f'<p>{E(j["x"])}</p><div class="row"><a class="btn" href="{E(j["u"])}" target="_blank" rel="nofollow noopener">'
            f'Apply on employer site</a><a class="meta" href="/contact/">Report</a>'
            f'<span class="meta">Source: {E(j.get("src", "Direct"))}</span></div></article>')


# ---------- job pages ----------
def job_page(j, all_jobs):
    path = f"/jobs/{j['slug']}/"
    posted = j["posted"]
    remote = j["l"] == "Remote"
    ld = {"@context": "https://schema.org", "@type": "JobPosting", "title": j["t"], "description": j["x"],
          "datePosted": posted, "employmentType": EMP.get(j["y"], "OTHER"),
          "hiringOrganization": {"@type": "Organization", "name": j["c"]}, "directApply": False,
          "url": SITE_URL + path, "identifier": {"@type": "PropertyValue", "name": j.get("src", "RemoteKazi"), "value": j["id"]}}
    # the page is taken down at the deadline or MAX_AGE_DAYS after posting, whichever comes first
    gone = (datetime.fromisoformat(posted).date() + timedelta(days=MAX_AGE_DAYS)).isoformat()
    ld["validThrough"] = min(j["deadline"], gone) if j.get("deadline") else gone
    if j["y"] == "Not stated":
        ld.pop("employmentType")
    if remote:
        ld["jobLocationType"] = "TELECOMMUTE"
        ld["applicantLocationRequirements"] = {"@type": "Country", "name": "Kenya"}
    else:
        ld["jobLocation"] = {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": j["l"],
                                                           "addressCountry": "KE"}}
    rel = [r for r in all_jobs if r["k"] == j["k"] and r["id"] != j["id"]][:4]
    relh = "".join(f'<li><a href="/jobs/{r["slug"]}/">{E(r["t"])}</a> · {E(r["c"])} · {E(r["l"])}</li>' for r in rel)
    body = (f'<p class="crumbs"><a href="/">Jobs</a> › {E(j["k"])}</p><h1>{E(j["t"])}</h1>'
            f'<p class="meta">{E(j["c"])} · {E(j["l"])} · Posted {E(posted)}'
            f'{" · Closes " + E(j["deadline"]) if j.get("deadline") else ""}</p>'
            f'<p>{tag_y(j)}<span class="tag">{E(j["k"])}</span>'
            f'{"<span class=tag>" + E(j["p"]) + "</span>" if j.get("p") else ""}</p>'
            f'{AD.format("Top banner")}<h2>About the role</h2>{"".join("<p>" + E(p) + "</p>" for p in re.split(r"\n\s*\n", j["x"]) if p.strip())}'
            f'<p><a class="btn" href="{E(j["u"])}" target="_blank" rel="nofollow noopener">Apply on the original page</a> '
            f'<a class="btn o" href="https://wa.me/?text={quote(j["t"] + " at " + j["c"] + " " + SITE_URL + path, safe="")}" target="_blank" rel="noopener">Share on WhatsApp</a></p>'
            f'<p class="meta">Source: {E(j.get("src", "Direct"))}. We link to the original listing; confirm every detail there. '
            f'Never pay a fee to get a job or interview. '
            f'<a href="mailto:{E(CONTACT_EMAIL)}?subject=Report%20job%3A%20{E(j["id"])}">Report this job</a></p>'
            f'{alerts_box()}{AD.format("In-content 300×250 / responsive")}'
            + (f'<h2>More {E(j["k"])} jobs</h2><ul>{relh}</ul>' if rel else "")
            + '<p><a href="/#jobs">← Back to all jobs</a></p>')
    write(path, page(f'{j["t"]} at {j["c"]} ({j["l"]}) | RemoteKazi', snip(j["x"]), path, body,
                     (f'<script type="application/ld+json">{json.dumps(ld).replace("</", "<\\/")}</script>'
                      if len(j["x"]) >= 150 else "")))     # Google needs a complete description


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
        "and to the police or the Communications Authority if you lost money. You can also report any listing on RemoteKazi using the link on its page.</p>"),
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
    "remote-work-from-kenya": ("Remote Work From Kenya: How to Start and Get Paid",
        "A beginner’s guide to finding remote work from Kenya, building trust with employers and receiving payments.",
        "<p>Remote work lets you earn from employers anywhere, but it rewards preparation. These steps work for most people starting out.</p>"
        "<h2>Check that you are eligible</h2><p>Read each advert for location rules. Some remote roles are open worldwide, some only to specific countries or time zones. "
        "Apply only where Kenya or Africa is allowed, and make sure you can work the hours required.</p>"
        "<h2>Set up your basics</h2><ul><li>Reliable internet and a backup, such as a mobile data bundle</li><li>A quiet workspace, headphones and a working laptop</li>"
        "<li>A professional email address and an up-to-date LinkedIn profile</li></ul>"
        "<h2>Build proof of your skills</h2><p>Employers abroad cannot visit your office, so show your work: a portfolio, writing samples, a GitHub page or a short "
        "video introduction. Start with smaller contracts to collect reviews.</p>"
        "<h2>Plan how you will be paid</h2><p>Ask the employer how they pay: bank transfer, a payment platform or mobile money. Compare the fees and exchange rates of "
        "each option before you agree, and keep records for tax purposes. Never pay to receive work or “unlock” earnings.</p>"),
    "cover-letter-tips-kenya": ("How to Write a Cover Letter That Gets Read",
        "A simple structure for a short, convincing cover letter for jobs in Kenya and remote roles.",
        "<p>A good cover letter is short, specific and addressed to the person hiring. Aim for one page, or about 250 to 350 words.</p>"
        "<h2>Use a simple structure</h2><ol><li><b>Opening:</b> name the job, and say in one sentence why you are a strong fit.</li>"
        "<li><b>Middle:</b> give two or three examples of results that match the advert, with numbers where you can.</li>"
        "<li><b>Close:</b> say you would welcome an interview, and thank the reader.</li></ol>"
        "<h2>Make it specific</h2><p>Mention the employer by name and say what attracts you to the role. Copying a template word for word is easy to spot.</p>"
        "<h2>Avoid common mistakes</h2><ul><li>Repeating your CV line by line</li><li>Spelling errors or the wrong company name</li>"
        "<li>Over-long paragraphs and vague claims such as “hardworking team player”</li></ul>"),
    "negotiate-salary-kenya": ("Salary Negotiation Basics for Job Seekers",
        "How to research pay, handle the salary question and negotiate an offer calmly.",
        "<p>Many people accept the first offer because negotiating feels uncomfortable. A calm, prepared conversation can make a real difference.</p>"
        "<h2>Do your research first</h2><p>Look at pay for similar roles in your county and industry, using job adverts, salary surveys and people you trust. "
        "Decide the lowest offer you would accept and the figure you would be happy with.</p>"
        "<h2>When asked for your expectation</h2><p>Give a range based on your research, and say it depends on the full package and responsibilities. "
        "Avoid stating your current pay unless it helps you.</p>"
        "<h2>Look at the whole offer</h2><ul><li>Basic pay, allowances and any bonus</li><li>Medical cover, leave days and pension</li>"
        "<li>Contract length, probation period and notice terms</li></ul>"
        "<h2>Get it in writing</h2><p>Ask for the offer letter and read it carefully before you resign from your current job. If something differs from what you discussed, raise it politely.</p>"),
}


def static_pages():
    for slug, (t, d, b) in GUIDES.items():
        write(f"/guides/{slug}/", page(f"{t} | RemoteKazi", d, f"/guides/{slug}/",
                                           f"<h1>{E(t)}</h1>{b}{AD.format('In-content ad')}<p><a href='/guides/'>← All guides</a></p>"))
    items = "".join(f'<li><a href="/guides/{s}/"><b>{E(t)}</b></a><br><span class="meta">{E(d)}</span></li>'
                    for s, (t, d, _) in GUIDES.items())
    write("/guides/index.html", page("Career Guides | RemoteKazi", "CV, interview and job-scam guides for Kenyan job seekers.",
                                     "/guides/", f"<h1>Career guides</h1><ul>{items}</ul>"))
    write("/about/", page("About RemoteKazi", "RemoteKazi lists jobs in Kenya and remote roles open to Kenyans.", "/about/",
        "<h1>About RemoteKazi</h1><p>RemoteKazi helps people in Kenya find jobs in Nairobi, Mombasa, Kisumu and beyond, plus remote roles "
        "open to applicants in Kenya. Browsing is free.</p><h2>How listings are collected</h2>"
        "<p>We gather vacancies from public job feeds and partner sources. Software summarises each listing in plain language, "
        "keeps only jobs relevant to Kenya, and flags adverts that look like scams. Every listing links to the original page, "
        "where you apply. Summaries can contain mistakes, so always check the original advert.</p>"
        "<h2>How we make money</h2><p>The site shows advertising and may carry sponsored listings, which are labelled. "
        "We never charge job seekers.</p>"
        f'<h2>Contact</h2><p><a href="mailto:{E(CONTACT_EMAIL)}">{E(CONTACT_EMAIL)}</a></p>'))
    write("/contact/", page("Contact RemoteKazi", "Contact RemoteKazi to report a job, an error or to advertise.", "/contact/",
        f'<h1>Contact us</h1><p>Email <a href="mailto:{E(CONTACT_EMAIL)}">{E(CONTACT_EMAIL)}</a>.</p>'
        "<ul><li><b>Report a scam or expired job:</b> include the page link.</li>"
        "<li><b>Employers:</b> ask about featured listings and advertising.</li>"
        "<li><b>Remove a listing:</b> tell us the link and we will take it down.</li></ul>"))
    write("/privacy/", page("Privacy Policy | RemoteKazi", "How RemoteKazi handles visitor data, cookies and advertising.", "/privacy/",
        f"<h1>Privacy Policy</h1><p class='meta'>Last updated {date.today().isoformat()}</p>"
        "<p>This policy explains what information RemoteKazi collects and how it is used, in line with the Kenya Data Protection Act, 2019.</p>"
        "<h2>What we collect</h2><p>We do not ask visitors to create accounts. We collect basic, aggregated visit data "
        "(pages viewed, device type, approximate location) through privacy-friendly analytics. If you email us, we keep your message and address to reply.</p>"
        "<h2>Cookies and advertising</h2><p>Third parties, including Google, may show ads on this site and use cookies to serve ads based on your "
        "visits here and to other sites. You can manage personalised ads at <a href='https://adssettings.google.com'>adssettings.google.com</a> "
        "or learn more at <a href='https://www.aboutads.info'>aboutads.info</a>.</p>"
        "<h2>Links to other sites</h2><p>Job listings link to external employer or job-board pages with their own privacy practices. "
        "Do not share sensitive details until you have verified the employer.</p>"
        "<h2>Your rights</h2><p>You may ask what data we hold about you, and request correction or deletion, by emailing "
        f"<a href='mailto:{E(CONTACT_EMAIL)}'>{E(CONTACT_EMAIL)}</a>.</p>"))
    write("/terms/", page("Terms of Use | RemoteKazi", "Terms for using RemoteKazi.", "/terms/",
        f"<h1>Terms of Use</h1><p class='meta'>Last updated {date.today().isoformat()}</p>"
        "<p>RemoteKazi is an information service. Listings come from third parties, we are not the employer, and we cannot guarantee "
        "that any job is genuine, available or accurate.</p><ul><li>Verify each employer before sharing personal information or applying.</li>"
        "<li>Never pay money to get a job or interview.</li><li>Sponsored listings and ads are labelled.</li>"
        "<li>We may remove any listing at any time.</li><li>To the extent allowed by law, RemoteKazi is not liable for losses arising from use of the site.</li></ul>"))


# ---------- blog: write posts as .md files in /posts ----------
def _link(m):
    text, url = m.group(1), m.group(2).strip()
    ok = url.startswith(("http://", "https://", "mailto:", "/", "#"))
    return f'<a href="{url}"' + (' rel="noopener"' if url.startswith("http") else "") + f'>{text}</a>' if ok else text


def _img(m):
    alt, url = m.group(1), m.group(2).strip()
    return f'<img src="{url}" alt="{alt}" loading="lazy" style="max-width:100%;height:auto;border-radius:12px">' \
        if url.startswith(("http://", "https://", "/")) else ""


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", _img, s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", _link, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<em>\1</em>", s)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", s)


def md_to_html(text):
    out, para, items, kind, tbl = [], [], [], None, []

    def flush_p():
        if para:
            joined = " ".join(para)
            fig = re.fullmatch(r"!\[([^\]]*)\]\(([^)\s]+)\)", joined.strip())
            if fig and fig.group(2).startswith(("http://", "https://", "/")):
                cap = f"<figcaption>{html.escape(fig.group(1), quote=False)}</figcaption>" if fig.group(1) else ""
                out.append(f'<figure><img src="{html.escape(fig.group(2))}" alt="{html.escape(fig.group(1))}" loading="lazy">{cap}</figure>')
            else:
                out.append("<p>" + inline(joined) + "</p>")
            para.clear()

    def flush_t():
        if tbl:
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in tbl]
            rows = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
            if rows:
                head = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
                body = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
                out.append(f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')
            tbl.clear()

    def flush_l():
        nonlocal kind
        if items:
            out.append(f"<{kind}>" + "".join(f"<li>{inline(i)}</li>" for i in items) + f"</{kind}>")
            items.clear()
            kind = None

    for raw in text.splitlines():
        ln = raw.rstrip()
        if ln.strip().startswith("|"):
            flush_p(); flush_l(); tbl.append(ln)
            continue
        flush_t()
        m = re.match(r"^(#{1,3})\s+(.*)", ln)
        ul = re.match(r"^\s*[-*]\s+(.*)", ln)
        ol = re.match(r"^\s*\d+[.)]\s+(.*)", ln)
        if not ln.strip():
            flush_p(); flush_l()
        elif m:
            flush_p(); flush_l()
            lvl = max(2, len(m.group(1)))        # # and ## become h2, ### becomes h3 (the page title is the h1)
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
        elif ul or ol:
            flush_p()
            want = "ul" if ul else "ol"
            if kind and kind != want:
                flush_l()
            kind = want
            items.append((ul or ol).group(1))
        elif ln.startswith(">"):
            flush_p(); flush_l()
            out.append("<blockquote>" + inline(ln.lstrip("> ")) + "</blockquote>")
        elif re.match(r"^-{3,}$", ln.strip()):
            flush_p(); flush_l(); out.append("<hr>")
        else:
            flush_l(); para.append(ln.strip())
    flush_p(); flush_l(); flush_t()
    return "\n".join(out)


def post_desc(meta, body):
    d = meta.get("description", "").strip()
    if d and d[-1] in ".!?’\"')":
        return snip(d, 160)
    # description missing or cut off mid-word: rebuild it from the summary or the article
    src = meta.get("summary") or re.sub(r"[#*\[\]()>`]", "", body)
    return snip(src)


def load_posts():
    posts = []
    for f in sorted(Path("posts").glob("*.md")):
        if f.name.startswith("_"):
            continue
        raw = f.read_text(encoding="utf-8")
        meta, body = {}, raw
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
        if m:
            for ln in m.group(1).splitlines():
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    meta[k.strip().lower()] = v.strip().strip('"').strip("'")
            body = m.group(2)
        try:
            when = date.fromisoformat(meta.get("date", ""))
        except ValueError:
            when = date.today()
        if when > date.today():                # scheduled posts go live on their date
            continue
        title = meta.get("title") or f.stem.replace("-", " ").title()
        words = len(re.findall(r"\w+", body))
        img = meta.get("image", "")
        if img.startswith("/"):
            img = SITE_URL + img
        try:
            upd = date.fromisoformat(meta.get("updated", ""))
        except ValueError:
            upd = None
        posts.append({"slug": slugify(f.stem), "title": title, "date": when, "updated": upd,
                      "author": meta.get("author", "RemoteKazi Team"), "summary": meta.get("summary", ""),
                      "caption": meta.get("image_caption", ""),
                      "desc": post_desc(meta, body),
                      "tag": meta.get("tag", "Career tips"), "image": img if img.startswith("http") else "",
                      "mins": max(1, round(words / 200)), "html": md_to_html(body)})
    return sorted(posts, key=lambda p: p["date"], reverse=True)


def share_bar(title, url):
    u, t = quote(url, safe=""), quote(title, safe="")
    links = [("WhatsApp", f"https://wa.me/?text={t}%20{u}"), ("Telegram", f"https://t.me/share/url?url={u}&text={t}"),
             ("X", f"https://twitter.com/intent/tweet?text={t}&url={u}"),
             ("Facebook", f"https://www.facebook.com/sharer/sharer.php?u={u}"),
             ("LinkedIn", f"https://www.linkedin.com/sharing/share-offsite/?url={u}")]
    return ('<div class="share"><b>Share:</b> ' +
            "".join(f'<a class="btn o" href="{l}" target="_blank" rel="noopener">{n}</a>' for n, l in links) + "</div>")


def post_card(p):
    thumb = f'<img class="thumb" src="{E(p["image"])}" alt="" loading="lazy">' if p["image"] else ""
    return (f'<a class="card post" href="/blog/{p["slug"]}/">{thumb}<span class="tag">{E(p["tag"])}</span>'
            f'<b>{E(p["title"])}</b><p class="meta">{E(p["desc"])}</p>'
            f'<span class="meta">{p["date"].strftime("%d %b %Y")} · {p["mins"]} min read</span></a>')


def build_blog(posts):
    for p in posts:
        path = f"/blog/{p['slug']}/"
        url = SITE_URL + path
        ld = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": p["title"], "description": p["desc"],
              "datePublished": p["date"].isoformat(), "dateModified": (p["updated"] or p["date"]).isoformat(),
              "mainEntityOfPage": url, "author": {"@type": "Person", "name": p["author"]},
              "publisher": {"@type": "Organization", "name": "RemoteKazi"}}
        if p["image"]:
            ld["image"] = p["image"]
        others = [o for o in posts if o["slug"] != p["slug"]][:3]
        body = (f'<p class="crumbs"><a href="/blog/">Blog</a> › {E(p["tag"])}</p><h1>{E(p["title"])}</h1>'
                f'<p class="meta byline">Published {p["date"].strftime("%d %b %Y")}'
                + (f' · Updated {p["updated"].strftime("%d %b %Y")}' if p["updated"] else "")
                + f' · By {E(p["author"])} · {p["mins"]} min read</p>'
                + f'<p class="lead">{inline(p["summary"] or p["desc"])}</p>'
                + (f'<figure class="hero"><img src="{E(p["image"])}" alt="{E(p["caption"] or p["title"])}">'
                   + (f'<figcaption>{E(p["caption"])}</figcaption>' if p["caption"] else "") + '</figure>' if p["image"] else "")
                + f'{p["html"]}{share_bar(p["title"], url)}{alerts_box()}'
                + (f'<h2>More from the blog</h2><div class="g3">{"".join(post_card(o) for o in others)}</div>' if others else "")
                + '<p><a class="btn" href="/#jobs">Browse latest jobs →</a></p>')
        write(path, page(f'{p["title"]} | RemoteKazi', p["desc"], path, body,
                         f'<script type="application/ld+json">{json.dumps(ld).replace("</", "<\\/")}</script>', p["image"] or None))
    cards = "".join(post_card(p) for p in posts) or "<p>New posts are coming soon.</p>"
    write("/blog/index.html", page("Blog: Job Search Tips for Kenya | RemoteKazi",
          "Career advice, CV tips and remote work guides for job seekers in Kenya.", "/blog/",
          f'<h1>Blog</h1><p class="meta">Career advice, CV tips and remote work guides.</p><div class="g3 posts">{cards}</div>'))
    items = "".join(f'<item><title>{E(p["title"])}</title><link>{SITE_URL}/blog/{p["slug"]}/</link>'
                    f'<guid>{SITE_URL}/blog/{p["slug"]}/</guid><pubDate>{p["date"].strftime("%a, %d %b %Y 00:00:00 +0300")}</pubDate>'
                    f'<description>{E(p["desc"])}</description></item>' for p in posts[:20])
    write("/feed.xml", f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>RemoteKazi Blog</title>'
                       f'<link>{SITE_URL}/blog/</link><description>Career advice for job seekers in Kenya</description>{items}</channel></rss>')
    # social post text for each of the newest articles, ready to copy
    lines = []
    for p in posts[:5]:
        lines += [f"📝 {p['title']}", p["desc"], f"{SITE_URL}/blog/{p['slug']}/", "#KenyaJobs #RemoteJobs #CareerTips", "", "---", ""]
    write("/social-posts.txt", "\n".join(lines))


def patch(text, tag, content):
    return re.sub(rf"<!--{tag}-->.*?<!--/{tag}-->", lambda _: f"<!--{tag}-->{content}<!--/{tag}-->", text, flags=re.S)


def main():
    idx = Path("index.html").read_text(encoding="utf-8")
    # take the main stylesheet from index.html, ignoring the small <style> that the HEAD block injects
    base = re.sub(r"<!--HEAD-->.*?<!--/HEAD-->", "", idx, flags=re.S)
    css = max(re.findall(r"<style>(.*?)</style>", base, re.S), key=len)
    if not SHOW_AD_PLACEHOLDERS:
        css += ".ad,aside{display:none!important}.main{grid-template-columns:minmax(0,1fr)!important}"
    css += (".w.prose{max-width:780px;padding-block:24px}.prose h2{margin:22px 0 8px}.prose li{margin:5px 0}"
            ".crumbs{font-size:14px;color:var(--muted)}footer a{margin-right:4px}.alerts{display:flex;gap:12px;flex-wrap:wrap;align-items:center;justify-content:space-between;background:var(--soft);border:1px solid var(--bd);border-radius:12px;padding:12px 14px;margin:14px 0}.row{display:flex;gap:8px;flex-wrap:wrap}footer p{margin:8px 0}.prose{font-size:18px;line-height:1.65}.byline{font-size:15px}.lead{font-size:clamp(19px,2.6vw,22px);line-height:1.55;font-weight:600;margin:14px 0 18px}figure{margin:18px 0}figure img{width:100%;height:auto;border-radius:14px;display:block}figcaption{font-size:14px;color:var(--muted);margin-top:8px}.tablewrap{overflow-x:auto;margin:16px 0}table{border-collapse:collapse;width:100%;font-size:16px}th,td{border:1px solid var(--bd);padding:10px 12px;text-align:left;vertical-align:top}th{background:var(--soft);color:var(--ac)}img.thumb{width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:10px;margin-bottom:10px;display:block}.share{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:24px 0}.share .btn{padding:8px 14px;font-size:15px}a.card.post{display:block;color:inherit;text-decoration:none}a.card.post b{display:block;font-size:19px;margin:8px 0 4px}blockquote{border-left:4px solid var(--ac);margin:16px 0;padding:4px 16px;color:var(--muted)}.prose img{margin:12px 0}.g3.posts{grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}.prose h1{font-size:clamp(28px,5vw,42px);line-height:1.15}")
    write("/style.css", css)

    by_id = {}
    for j in json.loads(Path("jobs.json").read_text(encoding="utf-8")):
        if j.get("src") != "Sample":
            by_id[j["id"]] = j          # one entry per job (latest copy wins)
    # jobs added by hand on the publish page live in manual_jobs.json; the list there is the source of truth
    try:
        manual = json.loads(Path("manual_jobs.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        manual = []
    manual_ids = {m.get("id") for m in manual}
    for k in [k for k, v in by_id.items() if v.get("src") == "Direct" and k not in manual_ids]:
        del by_id[k]                                    # removed from the list, so remove from the site
    for m in manual:
        if m.get("deadline") and m["deadline"] < date.today().isoformat():
            by_id.pop(m.get("id"), None)                # past its deadline
            continue
        m.setdefault("k", "Other"); m.setdefault("y", "Not stated"); m.setdefault("p", "")
        m.setdefault("deadline", ""); m.setdefault("f", 0); m["src"] = "Direct"
        m.setdefault("posted", date.today().isoformat())
        if m.get("id") and m.get("t") and m.get("c") and m.get("u") and m.get("x"):
            by_id[m["id"]] = m
    jobs = list(by_id.values())
    ordered = sorted(jobs, key=lambda j: (not j.get("f"), -datetime.fromisoformat(j["posted"]).toordinal()))
    shutil.rmtree("jobs", ignore_errors=True)
    for j in jobs:
        j["slug"] = f"{slugify(j['t'] + '-' + j['c'])}-{j['id'][:6]}"
    for j in jobs:
        job_page(j, jobs)
    Path("jobs.json").write_text(json.dumps(jobs, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.rmtree("guides", ignore_errors=True)
    for old in ("about", "contact", "privacy", "terms"):
        Path(f"{old}.html").unlink(missing_ok=True)      # old .html pages are replaced by /about/ style URLs
    static_pages()
    shutil.rmtree("blog", ignore_errors=True)
    posts = load_posts()
    build_blog(posts)

    # permanent redirects from the old .html addresses to the new clean ones (Cloudflare reads _redirects)
    old_new = [(f"/{n}.html", f"/{n}/") for n in ("about", "contact", "privacy", "terms")]
    old_new += [(f"/guides/{g}.html", f"/guides/{g}/") for g in GUIDES]
    old_new += [(f"/jobs/{j['slug']}.html", f"/jobs/{j['slug']}/") for j in jobs]
    old_new += [(f"/blog/{q['slug']}.html", f"/blog/{q['slug']}/") for q in posts]
    old_new += EXTRA_REDIRECTS
    write("/_redirects", "\n".join(f"{a} {b} 301" for a, b in old_new) + "\n")

    today = date.today().isoformat()
    # lastmod is the date a page really changed; Google ignores lastmod if every URL claims "today" on every run
    newest_job = max((j["posted"] for j in jobs), default=today)
    newest_post = max(((p["updated"] or p["date"]).isoformat() for p in posts), default=PAGES_UPDATED)
    sm = [("/", max(newest_job, newest_post)), ("/blog/", newest_post), ("/guides/", PAGES_UPDATED)]
    sm += [(f"/{n}/", PAGES_UPDATED) for n in ("about", "contact", "privacy", "terms")]
    sm += [(f"/guides/{s}/", PAGES_UPDATED) for s in GUIDES]
    sm += [(f"/jobs/{j['slug']}/", j["posted"]) for j in jobs]
    sm += [(f"/blog/{p['slug']}/", (p["updated"] or p["date"]).isoformat()) for p in posts]
    urls = [u for u, _ in sm]
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{SITE_URL}{u}</loc><lastmod>{d}</lastmod></url>" for u, d in sm) + "</urlset>")
    if ADSENSE_CLIENT:
        write("/ads.txt", f"google.com, {ADSENSE_CLIENT.replace('ca-', '')}, DIRECT, f08c47fec0942fa0\n")
    write("/robots.txt", f"User-agent: *\nAllow: /\nDisallow: /whatsapp-post.txt\nDisallow: /social-posts.txt\nDisallow: /publish.html\nSitemap: {SITE_URL}/sitemap.xml\n")
    ji = "".join(f'<item><title>{E(j["t"])} - {E(j["c"])} ({E(j["l"])})</title><link>{SITE_URL}/jobs/{j["slug"]}/</link>'
                 f'<guid>{SITE_URL}/jobs/{j["slug"]}/</guid><pubDate>{datetime.fromisoformat(j["posted"]).strftime("%a, %d %b %Y 00:00:00 +0300")}</pubDate>'
                 f'<description>{E(j["x"][:300])}</description></item>' for j in ordered[:50])
    write("/jobs.xml", '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>RemoteKazi Jobs</title>'
                       f'<link>{SITE_URL}/</link><description>Latest jobs in Kenya and remote jobs open to Kenyans</description>{ji}</channel></rss>')
    fresh = [j for j in ordered if j["posted"] == today][:8] or ordered[:8]
    lines = ["🔔 *New jobs on RemoteKazi*", ""]
    for j in fresh:
        lines += [f"💼 *{j['t']}*", f"{j['c']} · {j['l']}", f"{SITE_URL}/jobs/{j['slug']}/", ""]
    lines.append(f"More jobs: {SITE_URL}")
    write("/whatsapp-post.txt", "\n".join(lines))

    if jobs:  # write the first jobs into the HTML so search engines and AdSense can read them
        idx = patch(idx, "JOBS", "".join(card_html(j) for j in ordered[:20]))
        week = sum(1 for j in jobs if (date.today() - datetime.fromisoformat(j["posted"]).date()).days <= 7)
        vals = {"s1": len(jobs), "s2": sum(j["l"] == "Remote" for j in jobs), "s3": week,
                "s4": len({j.get("src", "Direct") for j in jobs})}
        for k, v in vals.items():
            idx = re.sub(rf'(<b id="{k}">)[^<]*(</b>)', rf'\g<1>{v}\g<2>', idx)
        idx = re.sub(r'(<span id="count">)[^<]*(</span>)', rf'\g<1>{len(jobs)} jobs found\g<2>', idx)
    idx = patch(idx, "FEATURED", featured_html())
    if posts:
        idx = patch(idx, "BLOG", "".join(post_card(p) for p in posts[:6]))
    else:   # no blog posts yet: show the guides instead
        idx = patch(idx, "BLOG", "".join(
            f'<a class="card post" href="/guides/{s}/"><span class="tag">Guide</span><b>{E(t)}</b><p class="meta">{E(d)}</p></a>'
            for s, (t, d, _) in list(GUIDES.items())[:6]))
    site_ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "@id": SITE_URL + "/#website", "url": SITE_URL + "/", "name": "RemoteKazi",
         "description": "Jobs in Kenya and remote jobs open to Kenyans", "inLanguage": "en-KE"},
        {"@type": "Organization", "@id": SITE_URL + "/#org", "name": "RemoteKazi", "url": SITE_URL + "/",
         "logo": SITE_URL + "/og-image.png", "email": CONTACT_EMAIL,
         "sameAs": [u for u in (WHATSAPP_URL, TELEGRAM_URL) if u]}]}
    home_head = head_extra("/") + f'<script type="application/ld+json">{json.dumps(site_ld)}</script>'
    for tag, content in (("NAV", NAV), ("HEAD", home_head), ("ALERTS", alerts_box()), ("FOOT", footer())):
        idx = patch(idx, tag, content)
    Path("index.html").write_text(idx, encoding="utf-8")
    print(f"Built {len(jobs)} job pages, {len(urls)} URLs in sitemap")


if __name__ == "__main__":
    main()
