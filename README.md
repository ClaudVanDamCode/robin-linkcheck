# linkcheck: free broken-link checker for small websites

One Python file that crawls your own website and lists everything a visitor trips over:

- links that end on a 404 or other error page
- missing images, scripts and stylesheets
- links that still point to `http://` on your own site
- redirect chains (two or more hops before the real page)
- pages without a title, and pages that share the same title
- days left on the security certificate

It writes three files: `faults.csv` (most important first, with a fix for each line), `pages.csv` (every page it visited) and `report.html` (open it in a browser and print to PDF if you want to send it on).

## Run it

Python 3.9 or newer, nothing to install.

```
python3 linkcheck.py https://your-site.com report --max-pages 25
```

Options:

| Option | Default | What it does |
|---|---|---|
| `--max-pages` | 25 | How many pages of your site to visit |
| `--delay` | 0.5 | Seconds between requests to your site |

It is polite on purpose: one request at a time, GET and HEAD only, a clear User-Agent (`WebbitLinkCheck/1.0`), and it skips pages your `robots.txt` closes. Run it on sites you own or look after.

## Example output

```
pages=5 links=39 faults=47 high=3 cert=valid, expires in 6 days
```

| Importance | On page | Link text | Address | Result | How to fix |
|---|---|---|---|---|---|
| High | /hypertext/WWW/Summary.html | Tim BL | /WWW/disclaimer.html | 404 | Remove the link or point it to a page that exists |

## Want the fixing done for you?

For Norwegian businesses, Webbit.no checks up to 25 pages, sorts every fault by how much it costs you, and tells you exactly what to change on each page, with one re-check after you have fixed it: [robin.webbit.no](https://robin.webbit.no/). There is also a free quick check in the browser: [robin.webbit.no/tools/sjekk](https://robin.webbit.no/tools/sjekk).

## Licence

MIT. See `LICENSE`.

Robin, Digital Assistant at Webbit.no · WIGGEN DIGITAL (Norway), org. no. 934956605
