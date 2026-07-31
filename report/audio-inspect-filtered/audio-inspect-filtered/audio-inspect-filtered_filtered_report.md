# audio-inspect-filtered — filtered CSV report

Generated: 2026-07-03

## Overview

- csv: `audio-inspect-filtered_20260703-153413.csv`  (mtime: 2026-07-03 15:34)
- rows: **93,081**  ·  unique clips: 93,081
- total: **149.18 h (8951.0 min)**  ·  mean clip duration: **5.77 s**
- empty transcripts: 0 (0.00%)
- transcript column: `text`

## Quantiles

- duration_s — p00=0.696, p25=4.46, p50=5.65, p75=6.98, p90=8.24, p99=10.2, p100=15.5
- char_len (>0) — p00=1, p25=45, p50=63, p75=80, p90=94, p99=116, p100=185
- word_len (>0) — p00=1, p25=7, p50=9, p75=11, p90=13, p99=14, p100=22
- ratio_sec_per_char — p00=0.0435, p25=0.0793, p50=0.0916, p75=0.109, p90=0.135, p99=0.48, p100=2.16
- ratio_sec_per_word — p00=0.339, p25=0.546, p50=0.642, p75=0.768, p90=0.95, p99=1.99, p100=2.18
- chars_per_sec — p00=0.463, p25=9.18, p50=10.9, p75=12.6, p90=14.1, p99=16.9, p100=23
- words_per_sec — p00=0.458, p25=1.3, p50=1.56, p75=1.83, p90=2.1, p99=2.62, p100=2.95

## Outlier counts & ranges (per ratio metric)

### ratio_sec_per_char  _(seconds / char)_

- n = **93,081**  ·  p1 = 0.05925  ·  p99 = 0.48  ·  p99.9 = 0.96  ·  Tukey low = 0.0349  ·  Tukey high = 0.1533

| rule | side | threshold | count | % | actual range |
|---|---|---:|---:|---:|---|
| > p99 | high | 0.48 | 930 | 0.999% | [0.486, 2.16] |
| > p99.9 | high | 0.96 | 93 | 0.100% | [0.972, 2.16] |
| > Tukey high | high | 0.1533 | 5,900 | 6.339% | [0.1533, 2.16] |
| < p1 | low | 0.05925 | 931 | 1.000% | [0.04347, 0.05924] |
| < Tukey low | low | 0.0349 | 0 | 0.000% | — |


### ratio_sec_per_word  _(seconds / word)_

- n = **93,081**  ·  p1 = 0.3816  ·  p99 = 1.992  ·  p99.9 = 2.184  ·  Tukey low = 0.213  ·  Tukey high = 1.101

| rule | side | threshold | count | % | actual range |
|---|---|---:|---:|---:|---|
| > p99 | high | 1.992 | 849 | 0.912% | [1.997, 2.184] |
| > p99.9 | high | 2.184 | 0 | 0.000% | — |
| > Tukey high | high | 1.101 | 5,374 | 5.773% | [1.102, 2.184] |
| < p1 | low | 0.3816 | 928 | 0.997% | [0.3394, 0.3813] |
| < Tukey low | low | 0.213 | 0 | 0.000% | — |


### chars_per_sec  _(chars / second)_

- n = **93,081**  ·  p1 = 2.083  ·  p99 = 16.88  ·  p99.9 = 19.11  ·  Tukey low = 4.043  ·  Tukey high = 17.75

| rule | side | threshold | count | % | actual range |
|---|---|---:|---:|---:|---|
| > p99 | high | 16.88 | 931 | 1.000% | [16.88, 23] |
| > p99.9 | high | 19.11 | 94 | 0.101% | [19.11, 23] |
| > Tukey high | high | 17.75 | 407 | 0.437% | [17.76, 23] |
| < p1 | low | 2.083 | 930 | 0.999% | [0.463, 2.058] |
| < Tukey low | low | 4.043 | 2,091 | 2.246% | [0.463, 4.042] |


### words_per_sec  _(words / second)_

- n = **93,081**  ·  p1 = 0.502  ·  p99 = 2.621  ·  p99.9 = 2.886  ·  Tukey low = 0.508  ·  Tukey high = 2.626

| rule | side | threshold | count | % | actual range |
|---|---|---:|---:|---:|---|
| > p99 | high | 2.621 | 928 | 0.997% | [2.622, 2.946] |
| > p99.9 | high | 2.886 | 92 | 0.099% | [2.888, 2.946] |
| > Tukey high | high | 2.626 | 916 | 0.984% | [2.628, 2.946] |
| < p1 | low | 0.502 | 849 | 0.912% | [0.4579, 0.5008] |
| < Tukey low | low | 0.508 | 954 | 1.025% | [0.4579, 0.5066] |


## Charts

![duration_hist.png](report/audio-inspect-filtered/audio-inspect-filtered/assets/duration_hist.png)
![sentence_length_chars_hist.png](report/audio-inspect-filtered/audio-inspect-filtered/assets/sentence_length_chars_hist.png)
![boxplot_distributions.png](report/audio-inspect-filtered/audio-inspect-filtered/assets/boxplot_distributions.png)
![boxplot_ratios.png](report/audio-inspect-filtered/audio-inspect-filtered/assets/boxplot_ratios.png)
![long_text_chars_per_second_hist_logx.png](report/audio-inspect-filtered/audio-inspect-filtered/assets/long_text_chars_per_second_hist_logx.png)
![ratio_sec_per_char_hist_logx.png](report/audio-inspect-filtered/audio-inspect-filtered/assets/ratio_sec_per_char_hist_logx.png)
![ratio_sec_per_word_hist_logx.png](report/audio-inspect-filtered/audio-inspect-filtered/assets/ratio_sec_per_word_hist_logx.png)
![chars_per_sec_hist_logx.png](report/audio-inspect-filtered/audio-inspect-filtered/assets/chars_per_sec_hist_logx.png)
![words_per_sec_hist_logx.png](report/audio-inspect-filtered/audio-inspect-filtered/assets/words_per_sec_hist_logx.png)

## Top 5 — audio long, text short

- `common_voice_de_38257292.mp3` · duration_s=2.160 · char_len=1 · s/char=2.160
  > K
- `common_voice_de_22085151.mp3` · duration_s=2.184 · char_len=2 · s/char=1.092
  > ja
- `common_voice_de_22133165.mp3` · duration_s=2.184 · char_len=2 · s/char=1.092
  > ja
- `common_voice_de_22204305.mp3` · duration_s=2.184 · char_len=2 · s/char=1.092
  > ja
- `common_voice_de_22135043.mp3` · duration_s=2.184 · char_len=2 · s/char=1.092
  > ja

## Top 5 — text long, audio short (char_len ≥ 30)

- `common_voice_de_43342658.mp3` · duration_s=4.608 · char_len=106 · chars/s=23.00
  > Im Mittelpunkt der politischen Arbeit stehen heute Menschenrechte, Umweltschutz und soziale Gerechtigkeit.
- `common_voice_de_38174092.mp3` · duration_s=3.924 · char_len=90 · chars/s=22.94
  > Die Temperaturschwankungen sind niedrig, sowohl im Tagesverlauf als auch im Jahresverlauf.
- `common_voice_de_17768616.mp3` · duration_s=4.896 · char_len=111 · chars/s=22.67
  > Leitungswasser ist billiger, enthält keinen Weichmacher und unterliegt strengeren Kontrollen als Mineralwasser.
- `common_voice_de_17616848.mp3` · duration_s=5.160 · char_len=115 · chars/s=22.29
  > Von siebzehn-hundert-zwölf bis neunzehn-hundert-achtzenh war Sankt Petersburg die Hauptstadt des Russischen Reichs.
- `common_voice_de_20313409.mp3` · duration_s=4.704 · char_len=104 · chars/s=22.11
  > Diese Vermittlungsstelle für Arbeitssuchende diente nicht zuletzt zur Disziplinierung der Belegschaften.