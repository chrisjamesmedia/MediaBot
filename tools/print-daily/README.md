# Print Signal Seeker every morning

Every public build writes a stable "latest" folder next to the dated editions:

| URL | What |
|---|---|
| https://chrisjamesmedia.github.io/MediaBot/signal-seeker/latest/ | redirects to today's web edition |
| https://chrisjamesmedia.github.io/MediaBot/signal-seeker/latest/print.pdf | today's print PDF (white paper, duplex "Sheet N of M" footers, even page count) |
| https://chrisjamesmedia.github.io/MediaBot/signal-seeker/latest/digital.pdf | today's digital PDF |
| https://chrisjamesmedia.github.io/MediaBot/signal-seeker/latest/latest.json | `{"date": "YYYY-MM-DD", "pages": {"print": N}, ...}`, used to check that it is today's paper |

Something on your side has to fetch that PDF and hand it to a printer. A website can't print on its own
and can't wake a sleeping computer. (OG Paperboy tried scheduling from an open browser tab, and its own
review recommended dropping that.) Pick one of the options below.

## Option A: a Mac (or Linux box) that is on in the morning (recommended)

`print-signal-seeker.sh` downloads `latest/print.pdf`, checks that it's a PDF dated today, prints it
double-sided (long edge) on Letter paper with `lp`, and records the date so it never prints twice.
If today's edition isn't up yet it prints nothing and exits; the next scheduled run will pick it up.
It installs nothing and needs only curl, lp and python3 (or plutil), which macOS already has.

1. Copy the script and make it executable:
   ```sh
   mkdir -p ~/signal-seeker
   cp print-signal-seeker.sh ~/signal-seeker/
   chmod +x ~/signal-seeker/print-signal-seeker.sh
   ```
2. Find your printer's queue name and check that it can print duplex:
   ```sh
   lpstat -p                       # queue names, e.g. HP_OfficeJet_Pro_9015e
   lpoptions -p QUEUE -l | grep -i duplex
   ```
3. Run a dry run, then one real test print:
   ```sh
   DRY_RUN=1 PRINTER=QUEUE ~/signal-seeker/print-signal-seeker.sh
   FORCE=1 PRINTER=QUEUE ~/signal-seeker/print-signal-seeker.sh
   ```
4. Schedule it with launchd. Edit `com.chrisjamesmedia.signalseeker.print.plist`: replace
   `YOUR_USER` and set `PRINTER` (leave it empty to use the default printer). Then:
   ```sh
   cp com.chrisjamesmedia.signalseeker.print.plist ~/Library/LaunchAgents/
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.chrisjamesmedia.signalseeker.print.plist
   launchctl kickstart gui/$(id -u)/com.chrisjamesmedia.signalseeker.print    # test it now
   ```
   It runs at 6:30 and 7:30 (the second run only matters if the paper was late). To stop it:
   `launchctl bootout gui/$(id -u)/com.chrisjamesmedia.signalseeker.print`.
5. If the Mac is asleep at 6:30, launchd runs the job when it wakes. To wake it on purpose, run
   `sudo pmset repeat wakeorpoweron MTWRFSU 06:25:00`. A laptop with its lid closed on battery won't
   wake for this.

Settings (environment variables): `PRINTER`, `MEDIA` (Letter/A4), `SIDES` (`two-sided-long-edge`, or
`one-sided` for a printer with no duplexer), `ALLOW_STALE=1` (print the newest edition even if it isn't
today's), `DRY_RUN=1`, `FORCE=1`, `STATE_DIR` (default `~/.signal-seeker`, which holds the log and a
copy of each printed PDF). The log is `~/.signal-seeker/print.log`.

**Linux:** the same script works with CUPS. Add a crontab line with `crontab -e`:
`30 6,7 * * * PRINTER=QUEUE $HOME/signal-seeker/print-signal-seeker.sh`

**Windows:** there's no `lp`. Use Task Scheduler with a PowerShell task that runs
`Invoke-WebRequest .../latest/print.pdf -OutFile $env:TEMP\ss.pdf` and then
`Start-Process -FilePath $env:TEMP\ss.pdf -Verb PrintTo -ArgumentList '"Printer Name"'`. This uses the
default PDF app, so set duplex as the default in that printer's preferences. Ask, and a .ps1 version can
be added here.

## Option B: email-to-printer (no computer needs to be on)

Many printers have their own email address and print attached PDFs:

- **HP ePrint** (HP Smart app → Printer settings → Print Anywhere / ePrint) gives an address like
  `something@hpeprint.com`. You choose the allowed senders. Duplex and paper size come from the
  printer's defaults in HP Smart, so turn on two-sided there.
- **Epson Connect Email Print** gives an address like `something@print.epson.com`, also with a sender
  allow-list. Set two-sided in Epson Connect's print settings for that address.
- **Brother** and **Canon** have similar services on some models (Brother "Email Print", Canon PRINT
  Business / "Mail Print"). Check your model.

This needs something that emails the PDF as an **attachment** every morning; a link isn't enough,
because these services print attachments. That can be a scheduled email step in the routine that builds
the paper, or a small cloud job (for example a scheduled GitHub Action that downloads `latest/print.pdf`
and mails it). Nothing like this is set up yet, because it would send email on your behalf and needs an
allowed sender address. Also, some ePrint services ignore duplex or scale pages, so do one test first.

## Option C: by hand

Bookmark `.../signal-seeker/latest/print.pdf`, open it, and press ⌘P. Choose two-sided, long-edge
binding, Letter, at 100% scale.

## To finish setting this up, tell us:

1. Which computer is on in the mornings (Mac, Windows or Linux), and whether it sleeps.
2. The printer's make and model, and whether it prints double-sided on its own (an automatic duplexer).
3. Whether the printer has HP ePrint, Epson Connect or another email-print address, if you'd rather not
   rely on a computer.
4. What time you want the paper printed, and whether to print on weekends.
5. Letter or A4.
