# Consumer Analysis using Google Maps Reviews & Sales Data


## Google Review Scrapper
### Installation
```bash
pip install playwright openpyxl pandas
playwright install
```

You can run the scraper right from the command line using either a time window or a fixed number of reviews. 

1. Url is set in env.py to avoid repeated copy-paste. If you want playwright to search for the place, set args.place.
2. Due to google map's restriction, we need to refresh the page once to load reviews.

### Option 1: Fetch by Count
Fetch an exact number of reviews regardless of date:
```bash
python google_reviews.py --place "Restaurant Name" --count 1000
```

### Option 2: Fetch by Period
Fetch all reviews within a specific time window:
```bash
python google_reviews.py --place "Restaurant Name" --period "4m"
```

The scraper supports a fast shorthand string using the `--period` (or `-t`) flag:

| Shorthand | Meaning |
|-----------|---------|
| `3h`      | 3 hours ago |
| `2d`      | 2 days ago |
| `1w`      | 1 week ago |
| `4m`      | 4 months ago |
| `1y`      | 1 year ago |
** Verbose format also accepted:  "3 hours", "1 month", "2 weeks", … **

---

## Output Location
Review data is exported automatically to the `./output/` directory as a formatted 10-column CSV table. 
The filename will look like: 
`reviews_<place>_<period>.csv`