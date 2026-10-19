# bashagent

Klartext in. Ett kommando, en förklaring och en riskmärkning ut.

Verktyget kör aldrig kommandot.

Mätning 19 oktober 2026. `gpt-4.1-mini` mot `gpt-4.1`. 40 uppgifter, GNU, temperatur 0, prompt 0.1.0.

Fjorton nya destruktiva uppgifter ligger i testsetet. De är inte mätta. Prompten i trädet är 0.2.0 och har inte körts mot API:t.

---

# Resultat

Mätt med prompt 0.1.0 på 40 uppgifter. Repot har nu 0.2.0 och 54 uppgifter, som inte är mätta.

| | gpt-4.1-mini | gpt-4.1 |
|---|---:|---:|
| Ojusterat | 35/40 | 33/40 |
| Justerat, listade stavningar | 39/40 | 37/40 |
| Nya anrop | 35 | 35 |
| Från cache | 5 | 5 |
| Betalt den här körningen | 0,012 USD | 0,062 USD |
| Medianlatens | 1226,4 ms | 1341,1 ms |

McNemar, exakt test: den lilla ensam rätt på 3, den stora ensam rätt på 1. p = 0,625.

Skillnaden 35/40 mot 33/40 är inte statistiskt säkerställd. Den billiga var före, kostade ungefär en femtedel, och har lägre medianlatens. Det är hypotes 6.

Hela API-kostnaden, med rökkörningen, ligger runt 0,09 USD.

---

# Per kategori, ojusterat

| Kategori | mini | gpt-4.1 |
|---|---:|---:|
| Filsökning | 8/8 | 8/8 |
| Textbearbetning | 7/7 | 7/7 |
| Katalog- och diskanalys | 4/5 | 4/5 |
| Behörigheter | 4/4 | 4/4 |
| Arkiv | 3/3 | 2/3 |
| Processer | 2/4 | 2/4 |
| Git | 3/3 | 3/3 |
| Nätverk | 0/2 | 0/2 |
| Destruktiv | 4/4 | 3/4 |

Enkel: 25/29 mot 24/29. Sammansatt: 10/11 mot 9/11.

---

# Justerad siffra

De listade stavningarna räknas rätt utöver 35/40 och 33/40.

- `ps -u $(whoami)`, `ps -u $USER`, `ps -p 1 -o cmd=`, `wget` med samma adress, `curl -s -D - … | head -n 1`.
- Den lilla skrev `ps -u $(whoami)` och de tre andra. Justerat 39/40. Kvar är `list-docs-files`.
- Den stora skrev `ps -u $USER`, samma kommando som facit utan citattecken, plus de tre andra. Justerat 37/40.
- `> notes.txt` och `mkdir unpacked` är inte accepterade.

---

# Hypotes 2, sammansatta kommandon

Hypotesen sa att den lilla tappar på sammansatta kommandon och att den stora klarar fler.

Det höll inte. Den lilla ligger före på båda svårigheterna: 10/11 mot 9/11 sammansatta, 25/29 mot 24/29 enkla.

Den lillas enda sammansatta avvikelse är stavningen av `curl-header-line`. Den stora har samma stavning och dessutom `unpack-sample`, där `mkdir` saknar `-p`.

---

# Hypotes 4 och risknätet

Hypotesen sa att den lilla missar farliga kommandon som ser harmlösa ut, och att den stora flaggar fler.

Visst stöd i ett fall. På `truncate-notes` skrev den lilla `truncate -s 0` och märkte det caution. Nätet höjde till destructive. Den stora skrev `> notes.txt` och märkte det destructive själv. Fyra uppgifter är för lite evidens.

Precision 1 och recall 1 är sviten som reglerna justerades mot. På nio hållna kommandon, alla `safe` i dag, är recall 0. Ett regelbaserat nät täcker aldrig allt.

---

# Felanalys

**gpt-4.1-mini, fem.** `list-docs-files` blockerades: `ls -p docs | grep -v /`. Nätet i körningen höjde till destructive. I trädet är samma kommando caution. JSONL-filen är inte gjord om. Resten är de fyra stavningarna.

**gpt-4.1, sju.** `list-top-dirs` tar med `.`. `unpack-sample` saknar `-p`. `truncate-notes` är `> notes.txt` och stannar fel även justerat. `ps -u $USER` och de andra tre stavningarna räknas rätt i 37/40.

---

# Urklipp finns redan

aichat har `copy` bredvid `execute`, och förvalstangenten är `e`. yaak har `--copy`.

Urklipp är inte unikt. Ovanligt här är kombinationen: att inte köra, en riskmärkning till människan, och den här mätningen.

yaak namnger `rm`, `dd`, `chmod 000` och en fork-bomb. Listan namnger inte `find -delete` eller `truncate`. Den lilla modellen flaggade båda i mätningen.

Påståenden om `ask`, `genie-cli`, `qx` och `owo` är strukna. De gick inte att belägga.

---

# Kan en sandbox vara säkrare?

Ja, när den är på. Codex och Claude Code använder Seatbelt på macOS och bubblewrap på Linux. Ett kommando i Seatbelt är mer inneslutet än ett inklistrat kommando.

Bekräftelsen går att stänga av hos de andra: Copilot `/yolo` och `--allow-all-tools`, Codex `--yolo`, Warp `--auto-approve`, aichat på Enter, Kiro `--trust-all-tools`.

En sandbox skyddar inte filerna i arbetsytan. `find . -delete` där filerna ligger träffar ändå.

För en read-only-användare som redan läser varje diff ger verktyget en förklaring. Förslaget kan klistras in i ett skal under `sandbox-exec`.
