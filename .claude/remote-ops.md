# Remote-Ops — סיכום סשן עמידוּת RC (2026-06-30)

> נשמר לבקשת עודד ("SAVE"). מסכם החלטות והבנות מסשן ארוך על: שליטה-מרחוק (RC)
> מהטלפון, עמידוּת לריסטרט, ה-Web UI כ"מעיר-סוכן", והגדרות Drive/גיבוי.
> תיעוד-תפעול. ראה גם חוק-הברזל (האצלה ל-Claude Code המקומי) ב-CLAUDE.md §0.

## עובדות-מכונה (Windows של עודד)
- שם מחשב: **DESKTOP-U15GPPN**. שני משתמשים: **Oded Kdoshim** (היעד) + Caesar.
- Python 3.14; `claude` הוא shim **`.cmd`** ב-PATH.
- ריפו ה-Web UI שוכפל ל: **`C:\Users\Oded Kdoshim\Desktop\claude-webui`** (ענף `claude/rc-p6es2u`).
- ⚠️ `C:\Users\Oded Kdoshim\Desktop\claude` = אפליקציה **אחרת** ("Electra FM Smart Care", פורט 8000) — **לא** הריפו. לא לבלבל.
- watchdog ב-Startup (`R10_watchdog_launch.vbs` → `r10_service_watchdog.py --loop`) מחזיק חיים **n8n (5678)** + **brain server (5765)**.
- גישה-מרחוק: **Chrome Remote Desktop** (שירות — זמין כבר במסך-נעילה).

## עמידוּת RC — נסגר ✅
הבעיה: ריסטרט לילי → סשן מקומי מת → רוטינת 1:00 נכשלת.
מה שהוטמע:
- **Autologon (Sysinternals)** — כניסה אוטומטית ל-Oded Kdoshim (סיסמה מוצפנת). **הוכח:** עלה לבד בלי PIN.
- **תיקיית Startup** (`...\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup`): קיצורים ל-**Claude Code** + **Outlook** → נפתחים בכל login.
- להשלים: Power → Sleep = **Never** (ב-AC).
- ממצא מפתח: פריטי Startup ושירותי-GUI רצים **רק אחרי login** — לא במסך-נעילה. לכן Autologon הכרחי לתרחיש 1:00 הלא-מאויש.

## ארכיטקטורת RC (מה עובד / מה לא)
- **יועץ-ענן** (claude.ai/code web — כמו הסשן הזה): תמיד נגיש מהנייד; קורא/כותב Drive; **לא** רואה/יוצר/מפעיל רוטינות מקומיות (ה-MCP כאן ענן-בלבד — נבדק: 0 רוטינות, 2 סביבות-ענן).
- **רוטינות Local**: ה-RC בפועל; רצות רק כשהמחשב ער. נוצרות **מדסקטופ בלבד**; מהנייד רק מפעילים קיימת.
- **הגשר** (`_CODE_DROP__MSG`): **לא** מעיר סשן מקומי (push לא עובד — אומת ע"י עודד).
- **רעיון של עודד (מאומץ):** רוטינה מתוזמנת כל כמה שעות שפותחת סשן → תמיד יש סשן פתוח "להתלבש" עליו מהנייד.

## Web UI כ"מעיר-סוכן" (חלקי — פתוח)
- `server.py` (Flask, פורט **8002**, מוגן Tailscale): `/submit` מריץ `claude -p` מקומי בתיקיית `CLAUDE_WORKDIR`.
- שופר לנייד: כפתור-שליחה גדול, מצב-ריצה + מונה-שניות, Enter חכם למגע, רספונסיבי (100dvh, safe-area, יעדי-מגע 44px).
- תוקן: נתיבי `tempfile` (Windows), הרצת `claude.cmd` (דרך `cmd.exe`), פרומפט דרך **stdin + UTF-8**.
- ❗ **פתוח:** claude רץ ומסתיים תקין אבל מחזיר **פלט ריק** ב-Windows; הסיבה לא נפתרה (הופסק לבקשת עודד). אם חוזרים — לאבחן עם `claude -p "say hi"` ו-`echo hi | claude -p` ישירות, לראות אם claude בכלל מדפיס ל-stdout.
- קונפיג (env vars): `CLAUDE_BIN`, `CLAUDE_WORKDIR` (ברירת-מחדל `G:\My Drive\ROTHSCHILD_10_CORE`), `CLAUDE_PERMISSION_MODE` (`bypassPermissions`).

## Drive — החלטה
- להישאר **Stream** + לסמן `ROTHSCHILD_10_CORE` כ-**Available offline**. **לא** לעבור Mirror (משנה `G:\`→`C:\` ושובר את כל נתיבי הרוטינות).
- commit מדי פעם = נקודות-חזרה; לא קריטי לבטיחות כי Drive מגבה את הקבצים.

## משימות פתוחות
1. **גיבוי 3-2-1** → D: (`robocopy /E` + תצלום מתוארך) + כונן נייד 2TB. חסר: יעד ב-D:, אות-כונן 2TB, תדירות+שעה (לא לחפוף 1:00).
2. **ניקוי פריט-Startup שבור של WSA** (`WsaClient.exe`) — הואצל ל-Claude Code המקומי.
3. (אופציונלי) פתרון הפלט-הריק של הרצת-הסוכן ב-Web UI.
