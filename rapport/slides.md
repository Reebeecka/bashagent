# bashagent

Klartext in. Ett kommando, en förklaring och en riskmärkning ut.

Verktyget kör aldrig kommandot.

Mätning 19 oktober 2026. `gpt-4.1-mini` mot `gpt-4.1`. 40 uppgifter, GNU, temperatur 0.

---

# Resultat

| | gpt-4.1-mini | gpt-4.1 |
|---|---:|---:|
| Höll på det som jämfördes | 35/40 | 33/40 |
| Nya anrop | 35 | 35 |
| Från cache | 5 | 5 |
| Betalt den här körningen | 0,012 USD | 0,062 USD |

Fem procentenheter. Den billiga var före och kostade ungefär en femtedel.

Skillnaden mellan modellerna är inte statistiskt säkerställd. Vid 40 uppgifter är en skillnad under ungefär 15 procentenheter inte skiljbar från brus.

Hela API-kostnaden, med rökkörningen, ligger runt 0,09 USD.

---

# Upplägg

Läsande uppgifter kördes i varsin Debian-container. Utdata jämfördes.

Destruktiva kommandon kördes inte.

Övriga jämfördes som text mot facit. Samma kommando med annan stavning räknas då som avvikelse.

Hypoteserna skrevs innan första mätanropet. Huvudsiffran gäller GNU. macOS är inte mätt.

---

# Felanalys: gpt-4.1-mini

Fem avvikelser. 40 − 5 = 35/40.

**list-docs-files**, blocked/risk. `ls -p docs | grep -v /` mot `find docs -maxdepth 1 -type f`. Risknätet höjde till destructive på snedstrecket. Falskt larm.

Samma kommando, annan stavning. Räknas i femman, och är inte modellfel:

- **ps-current-user:** `ps -u $(whoami)` mot `ps -u "$USER"`
- **ps-pid-one:** `ps -p 1 -o cmd=` mot `ps -p 1 -o args=`
- **curl-save-original:** `wget` mot `curl -O`, samma adress
- **curl-header-line:** `curl -s -D - … | head -n 1` mot `curl -sI … | head -n 1`. Kördes inte.

---

# Felanalys: gpt-4.1

Sju avvikelser. 40 − 7 = 33/40.

- **list-top-dirs:** `find . -maxdepth 1 -type d`. `.` kommer med. Facit har `-mindepth 1`.
- **unpack-sample:** kommandona skiljer på `-p`. Filsystemsskillnaden är inte diagnostiserad. Räknas i 33/40.
- **truncate-notes:** `> notes.txt` mot `truncate -s 0 notes.txt`. Bara den stora. Båda destructive. Mini träffade truncate.
- Samma två `ps` och samma två `curl` som hos mini, inklusive **curl-header-line**.

---

# Hypoteserna

1. Enkla kommandon, ungefär lika. Stämmer. Båda klarade i stort sett alla `find`.
2. Den lilla tappar på sammansatta. Stämmer inte på totalsiffran. 35 mot 33.
3. Skillnaden blir för liten, och den billiga räcker. Stämmer.
4. Den lilla missar `find -delete` och `truncate`. Stämmer inte. Den flaggade båda, plus `git clean` och `rm`.
5. GNU-flaggor på macOS. Inte mätt.
6. Priset räknas. Stämmer. Ungefär en femtedel.

---

# Urklipp finns redan

`ask` kör aldrig och kopierar på en tangent. `genie-cli` kopierar som standard. `qx`, `owo`, aichat och `yaak` har samma väg.

Urklipp är inte unikt.

Ovanligt i analysen är kombinationen: att inte köra, en riskmärkning till människan, och en publicerad mätning.

`yaak` blockerar `rm` och `dd`. Listan träffar inte `find -delete` eller `truncate`. Den lilla modellen flaggade båda.

---

# Kan en sandbox vara säkrare?

Ja, i ett enskilt kommando, om den är på. Ett kommando i Seatbelt är mer inneslutet än ett inklistrat kommando.

Bekräftelsen går att stänga av hos de andra. Copilots sandbox är av som standard. Codex har `--full-auto` och Full Access. Warps auto-approve kringgår denylistan som standard. aichat kör på Enter. Flaggorna heter `--yolo`, `--allow-all`, `--trust-all-tools`, `-y` och `auto_run`.

En sandbox skyddar inte filerna inuti arbetsytan. Den hindrar kommandot från att lämna katalogen. `find . -delete` i rätt katalog är lika förödande sandboxat.

För en disciplinerad read-only-användare ger verktyget ingen fördel. Bara en förklaring. Förslaget kan fortfarande klistras in i ett skal som redan körs under `sandbox-exec`.
