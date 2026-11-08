# FMC Resourcepack

Icons, Menü-Stil (dunkle Buttons, Hintergrund, Trennlinien) und Fortschrittsbalken für die Dialoge und Menüs
des FMC-Plugins. Das Pack wird **nur an Spieler mit der Permission `fmc.resourcepack`** geschickt (das Team) und
ist für diese **Pflicht**. Alle anderen Spieler sehen weiterhin das normale Minecraft.

## Wo liegt was?

| Was | Wo |
|---|---|
| **Quelle (hier arbeiten!)** | Ordner `FMC-Resourcepack/` im privaten FMC-Repo, wie alle anderen Plugins |
| Öffentliche Kopie (nur zum Ausliefern) | https://github.com/g0dlike2x/FMC-Resourcepack, wird **automatisch** aus dem FMC-Repo gespiegelt, dort nicht von Hand ändern |
| Fertige ZIP, die der Server verteilt | https://github.com/g0dlike2x/FMC-Resourcepack/releases/download/latest/FMC-Resourcepack.zip |
| Arbeitskopie | Ordner `FMC-Resourcepack/` im lokalen Clone des FMC-Repos |

Warum zwei Repos? Spieler-Clients laden die ZIP ohne Login herunter. Das geht nur aus einem **öffentlichen** Repo, das
FMC-Repo ist privat. Wer Zugriff auf das FMC-Repo hat, kann das Pack ändern. Ein Zugriff auf das öffentliche Repo
ist dafür nicht nötig.
| Server-Seite im FMC-Plugin | Paket `com.example.myplugin.resourcepack` (`ResourcePackManager`, `ResourcePackListener`, `ResourcePackCommand`, `ResourcePackModule`) |
| Icon-Zeichen im Plugin | `FMC-Plugin/src/main/java/com/example/myplugin/ui/UiIcon.java` (**wird von hier aus generiert**, nicht von Hand ändern) |
| Einstellungen | `settings/config.yml` des Plugins, Abschnitt `resourcepack:` |

Die ZIP liegt immer unter **derselben URL** (Release mit dem Tag `latest`). Bei jedem Update wird dieses Release
ersetzt, die URL ändert sich nie.

## So kommt das Pack auf den Server

```
Änderung im FMC-Repo pushen
   │  Action "Resourcepack Sync" (FMC-Repo)
   ▼
Öffentliches Repo FMC-Resourcepack wird aktualisiert
   │  Action "Release Resourcepack" (öffentliches Repo)
   ▼
ZIP gebaut, Release "latest" ersetzt
   │
   ▼  /fmcpack reload (auf dem Server)
Plugin lädt die ZIP, berechnet den SHA-1 und schickt das Pack
   ▼
Spieler mit fmc.resourcepack bekommen es (beim Join und nach /fmcpack reload)
```

Sobald das Pack gespiegelt wurde, geht eine **Discord-Nachricht** an denselben Webhook wie die Plugin-Builds
(Titel „🎨 Resourcepack aktualisiert", mit Autor, Commit, geänderten Dateien und dem Hinweis auf `/fmcpack reload`).
Schlägt der Sync fehl, kommt stattdessen „❌ Resourcepack-Sync fehlgeschlagen" mit Link zum Log.

Der SHA-1-Hash wird vom Plugin **selbst aus der heruntergeladenen ZIP berechnet**. Du musst ihn nirgends eintragen.
Weil der Client Packs über den Hash zwischenspeichert, lädt er bei jeder Änderung automatisch die neue Version.

## Pack ändern und auf den Server bringen (Schritt für Schritt)

1. **Ändern.** Icons und Farben stehen in `tools/generate_icons.py`, Buttons/Hintergründe in `tools/ui_textures.py`.
2. **Neu erzeugen** (im Ordner `FMC-Resourcepack`):
   ```
   python tools/generate_icons.py
   ```
   Das schreibt alle PNGs und `icons.json` nach `pack/` und eine Vorschau nach `dist/preview.png`.
   Außerdem schreibt es `UiIcon.java` in das FMC-Plugin (siehe unten).
3. **Vorschau ansehen**: `dist/preview.png` enthält alle Icons.
4. **Committen und pushen** im **FMC-Repo** (`FMC-Resourcepack/pack/`, `tools/` und, falls neue Icons dazukamen,
   auch `FMC-Plugin/.../ui/UiIcon.java`). Danach laufen nacheinander zwei Actions:
   *Resourcepack Sync* im FMC-Repo und *Release Resourcepack* im öffentlichen Repo. Zusammen dauert das etwa eine
   Minute, beide müssen ein grünes Häkchen haben.
5. **Auf dem Server** `/fmcpack reload` ausführen. Das Plugin lädt die neue ZIP, und alle online berechtigten Spieler
   bekommen sie sofort. Wer später joint, bekommt ohnehin die aktuelle Version.
6. Neue Icons bedeuten auch eine neue `UiIcon.java`. Die steckt im Plugin und wird erst mit dem **nächsten
   Plugin-Deploy** wirksam. Da ein Push im FMC-Repo das Plugin ohnehin neu baut, passiert das automatisch.

Nur Texturen/Farben geändert und keine neuen Icons? Dann reichen die Schritte 1 bis 5.

## Einmalige Einrichtung (Sync-Token)

Die Action *Resourcepack Sync* darf nur dann ins öffentliche Repo schreiben, wenn dafür ein Zugangs-Token hinterlegt ist.
Ohne Token zeigt sie nur eine gelbe Warnung und spiegelt nichts.

1. GitHub → Profilbild → *Settings* → *Developer settings* → *Personal access tokens* → *Fine-grained tokens* →
   *Generate new token*.
2. *Repository access*: **Only select repositories** → `g0dlike2x/FMC-Resourcepack`.
3. *Permissions* → *Repository permissions*: **Contents: Read and write**. Wird `release.yml` später geändert,
   zusätzlich **Workflows: Read and write**.
4. Token erzeugen und kopieren.
5. Im **privaten FMC-Repo** → *Settings* → *Secrets and variables* → *Actions* → *New repository secret*:
   Name **`RESOURCEPACK_PUSH_TOKEN`**, Wert = der Token.
6. *Actions* → *Resourcepack Sync* → *Run workflow*, um den ersten Abgleich auszulösen.

Läuft der Token ab, wird die Action wieder gelb bzw. rot. Dann einen neuen Token erzeugen und das Secret ersetzen.

Notlösung ohne Token: Änderungen von Hand in das öffentliche Repo übertragen. Dafür braucht die Person dort
Schreibrechte (*Settings* → *Collaborators*).

## Neues Icon hinzufügen

1. In `tools/generate_icons.py` eine Funktion `icon_xyz()` schreiben (als Vorlage dient ein vorhandenes Icon).
2. Den Eintrag **ganz hinten** in `_ICON_LIST` anhängen, zum Beispiel `("xyz", icon_xyz)`.
   **Nie in der Mitte einfügen oder umsortieren**: die Zeichen (`U+E000`, `U+E001` …) werden nach der Reihenfolge
   vergeben, sonst ändert sich das Aussehen aller Icons dahinter.
3. `python tools/generate_icons.py` ausführen, Vorschau prüfen.
4. Alles zusammen im FMC-Repo committen und pushen: `FMC-Resourcepack/` **und** die geänderte `UiIcon.java`.

Der Pfad zum Plugin ist standardmäßig der Nachbarordner `..\FMC-Plugin`. Liegt es woanders, vorher die
Umgebungsvariable `FMC_PLUGIN_DIR` setzen. Ist der Ordner nicht da, wird `UiIcon.java` einfach nicht geschrieben.

## Icons im Plugin benutzen

```java
Component text = UiKit.row(                          // Zeile aus mehreren Teilen
    UiKit.icon(UiIcon.BANK),                         // Icon (immer weiß, nicht fett)
    UiKit.space(4),                                  // 4 Pixel Abstand
    Component.text("Bank", NamedTextColor.WHITE));

Component bar = UiKit.bar(64, 20, from, to);        // Fortschrittsbalken aus 20 Segmenten
```

Wichtig:
- **Text nie mit `.append(...)` an ein Icon hängen**, immer `UiKit.row(...)` benutzen. Kinder erben die Schrift des
  Elternteils, der Text erschiene sonst in der Icon-Schrift als Kästchen.
- Icons sind fertig eingefärbt und werden mit **weißer** Textfarbe benutzt, sonst werden sie getönt.
- Ohne geladenes Pack erscheinen Platzhalter-Kästchen. Vorher mit `plugin.getResourcePackManager().hasPack(player)`
  prüfen und sonst eine schlichte Variante ohne Icons zeigen.
- Bedrock-Spieler (Name beginnt mit `.`) bekommen das Pack nicht.

## Neues Menü bauen (PanelMenu)

Alle Menüs im FMC-Stil werden mit `PanelMenu` gebaut (`FMC-Plugin/.../ui/PanelMenu.java`). Das Panel passt seine Höhe
automatisch an den Inhalt an. Ein komplettes Menü:

```java
PanelMenu.create(plugin)
    .title(UiIcon.BANK, "Bank")                                   // Titel oben (außerhalb des Rahmens)
    .card(                                                        // optional: Profilkarte mit Stern
        UiLine.inCard().text(player.getName(), NamedTextColor.WHITE, true),
        UiLine.inCard().icon(UiIcon.TOKENS).gap(2).text("12.500", NamedTextColor.YELLOW, false),
        null)                                                     // null = leere Zeile
    .line(UiLine.create().to(8).text("Freier Text unter der Karte"))   // optional: weitere Zeilen
    .button(UiIcon.TOKENS, "Einzahlen", p -> deposit(p))          // Buttons im Raster (2 Spalten)
    .button(UiIcon.TOKENS, "Abheben", p -> withdraw(p))
    .fallback(p -> openSimpleBankMenu(p))                         // für Spieler OHNE Pack
    .open(player);
```

Weitere Optionen: `.columns(1)`, `.closeButton(false)`, `.cardStar(false)`, `.chevron(false)`, `.blank()`.
Ein fertiges Beispiel zum Abschauen ist `FmcMenuCommand` (`/fmcmenu`). Für ein neues Menü genügt es, diese Klasse zu
kopieren und die Inhalte auszutauschen.

**Wie es funktioniert (nur wichtig, wenn man am Stil selbst arbeitet):**
- Der Rahmen ist ein Hintergrundbild aus Kacheln der Schrift, das in der ersten Textzeile steht und nach unten über alle
  weiteren Zeilen und die echten Buttons hinausragt. Die Texte liegen darüber und werden mit `UiLine` pixelgenau
  platziert (`to(x)`, `gap(px)`, `right(...)`).
- **Wichtig:** Minecraft lädt Schriftbilder nur bis **256 x 256 Pixel**. Größere erscheinen als weißes Kästchen. Deshalb
  besteht der Rahmen aus Kacheln (je 64 x 12 Pixel, in 12er-Reihen gestapelt, bis 288 Pixel Höhe).
- Alle Textzeilen müssen **dieselbe Gesamtbreite** haben (`build(W)`, macht `PanelMenu` selbst), sonst zentriert Minecraft sie
  unterschiedlich. Eine Zeile ist 9 Pixel hoch.
- Die Maße des Vanilla-Layouts (Abstand zu den Buttons, Buttonhöhe) stehen als Konstanten oben in `PanelMenu`. Weicht
  ein Menü im Spiel ab (Buttons sitzen zu hoch/tief im Rahmen), nur dort `BUTTON_GAP` o. Ä. anpassen.
- Die Breiten kommen aus `FontMetrics.java` (Minecraft-Schrift) und `UiIcon.advance()` (Icons). Beide Dateien werden
  erzeugt: `generate_icons.py` für die Icons, `python tools/gen_font_widths.py <client.jar>` für die Schrift (nur
  nach einem Minecraft-Update mit geänderter Schrift nötig).
- Aussehen von Rahmen, Karte und Stern: `make_panel_tile()` und `make_card_tile()` in `generate_icons.py`.
## Panel-Themes (/lager, /warp, /farmwelt)

Neben dem klassischen Stil (rote Linie) gibt es verzierte Themes: Rahmen mit Glow, Verzierungen an den Seiten und in den
unteren Ecken, Banner mit Ornament und Titelbild, Karte mit Itembox und dunkle Buttons mit farbiger Hervorhebung.
Alles wird in `tools/amethyst_theme.py` gezeichnet (Liste `THEMES`, von `generate_icons.py` mit aufgerufen).

| Theme | Menü | Look | Font | Dateien | Java |
|---|---|---|---|---|---|
| `PanelTheme.AMETHYST` | /lager | lila, Kristalle, Truhe | `fmc:icons` | `am_*.png` | `UiIcon.AM_*` |
| `PanelTheme.WARP` | /warp | türkis, Enderperlen, Endportal mit Enderauge, Endstein | `fmc:warp` | `wp_*.png` | `UiIcon.WP_*` |
| `PanelTheme.FARMWELT` | /farmwelt | grün, Grasblöcke, Baum, Wasser, Blumen | `fmc:farmwelt` | `fw_*.png` | `UiIcon.FW_*` |

Alle Themes benutzen **dieselben Zeichen** (U+ED00 bis U+F6xx); Amethyst liegt in `fmc:icons`, jedes weitere Theme in
einer eigenen Font (`pack/assets/fmc/font/<font>.json`). Das Plugin wählt die Font über `PanelTheme.font()`. Gleiche Teile
(Rahmen, Karte, Buttons, X) haben in allen Themes denselben Vorschub, deshalb gibt es `WP_`/`FW_`-Konstanten nur für das,
was vom Bild abhängt (Ecken, Ornament, Titel, Hintergrundbilder, Untertitelfarbe).

```java
PanelMenu.create(plugin)
    .title(...)
    .banner(PanelTheme.WARP, UiIcon.WP_TITLE_WARPS, UiIcon.WP_TITLE_WARPS_ADVANCE, "WÄHLE DEIN REISEZIEL")
    .cardGlyph(UiIcon.WP_CARD_GLYPH, UiIcon.WP_CARD_GLYPH_ADVANCE)   // Symbol in der Itembox
    .card(zeile1, zeile2, zeile3)        // Textzeilen mit UiLine.create().to(UiIcon.AM_NAME_X) beginnen
    .button(...)
    .emphasizeLast()                     // optional: letzter Button hervorgehoben
    .open(player);
```

`.banner(titel, vorschub, untertitel)` ohne Theme nimmt Amethyst (so benutzt es das Lager).

- Ohne `.banner(...)` geht ein Theme auch mit `.theme(PanelTheme.WARP)`; dann gibt es Ecken, aber kein Ornament.
- Neues Titelbild: Text in `titles` des Themes (`amethyst_theme.py`) eintragen, `generate_icons.py` ausführen, danach gibt
  es `UiIcon.<PRÄFIX>_TITLE_<TEXT>` und `..._ADVANCE`. Die Pixelschrift (`FONT5X7`) kennt A bis Z, Ziffern und `/ % - .`.
- Die unteren Ecken sind pro Panelhöhe ein eigenes Zeichen (U+F200 bis U+F40D). Die letzte Button-Reihe sollte
  nicht bis in die unteren Ecken reichen (links/rechts je ca. 25 Pixel frei), sonst überlappen sich Verzierung und Button.
  Deshalb hat /farmwelt zwei Spalten (End sitzt mittig in der letzten Reihe), und /warp passt am besten bei einer
  ungeraden Zahl von Zielen.
- Das Theme braucht oben vier Leerzeilen (Ornament ragt aus dem Rahmen) und vier Kopfzeilen. Sitzt das Panel im Spiel nicht
  mittig: `AM_CENTER_PAD_LINES` in `amethyst_theme.py` ändern.
- **Hintergrundbild:** Liegt ein Rahmenbild vor (`art/<theme>_panel.png`: Rahmen mit Ornament und Ecken, innen
  durchsichtig), skaliert `amethyst_theme.py` es so, dass die Öffnung 256 Pixel breit ist, dehnt die Mitte auf die
  Menühöhe, füllt das Innere mit Verlauf und Schein und schneidet es in Kacheln (4 Spalten, `U+F600`, je Höhe ein Block
  von 32 Zeichen). Gebaut wird es für jede Höhe in `bg_heights` des Themes (Lager 192, Warp 165/192/219 = 5 bis 10
  Ziele, Farmwelt 138). Menüs mit anderer Höhe bekommen den Kachelrahmen mit einzelnen Verzierungen. Die Höhe eines
  Menüs ist `lastLabelLine * 9 + 15 + 6` (siehe `preview_height()` in `amethyst_theme.py`).
- **KI-Bilder:** Ornament, Ecken, Titel und Rahmen sind mit der OpenAI-Bild-API erzeugte Bilder (`art/*.png`, Prompts in
  `art/prompts.json`). `OPENAI_API_KEY` als Umgebungsvariable setzen (nie ins Repo!), dann für ein ganzes Theme
  `python tools/ai_art.py theme warp` (bzw. `farmwelt`), oder einzeln `python tools/ai_art.py gen <name>` (Rohbild nach
  `art/raw/`, nicht im Repo) und `python tools/ai_art.py prep <name>` (zuschneiden und verkleinern nach `art/<name>.png`,
  Breite aus `prep_width`). Danach `python tools/generate_icons.py` und die Vorschau prüfen.
  Achtung bei Titeln: Weiße Buchstabenflächen kommen von der API oft durchsichtig zurück (der Titel ist dann im Spiel
  kaum lesbar). Deshalb im Prompt eine farbige, deckende Füllung verlangen (siehe `warps_title`).
- **Ohne KI-Bild:** Beim Warp- und Farmwelt-Theme zeichnet `tools/theme_art.py` einen Ersatz (Blöcke, Enderperle,
  Enderauge, Baum, Blumen); ohne Rahmenbild gibt es den Kachelrahmen. Ist ein Rahmenbild unbrauchbar (Öffnung nicht
  geschlossen), gibt es eine Warnung und ebenfalls den Kachelrahmen. Ohne Titelbild (`art/<text>_title.png`) wird der Titel
  in Pixelschrift gezeichnet. Das Lager (Amethyst) braucht seine Bilder zwingend.
- `dist/preview_<theme>.png` zeigt je Theme eine Vorschau des Menüs (Näherung mit einfacher Schrift).
- Offen/ungeprüft im Spiel: Position der Zeichen untereinander (Ornament, Titel, Untertitel, Ecken), Überlagerung der
  Zeichen innerhalb einer Zeile und der Abstand der Karte zu den Buttons.

## Kisten-GUIs (ChestGui)

Inventar-Menüs (Kisten) bekommen ihr Design über den Titel: ein Zeichen der Font `fmc:icons` legt ein Hintergrundbild
über die ganze Kiste, die Items bleiben normale, klickbare Items. Aktuell gestaltet: `/enderchest` (`U+EA00`, 54 Slots)
und `/bank` (`U+EA01`, 27 Slots).

- Bilder zeichnen: `tools/chest_textures.py` (1 Bildpixel = 1 GUI-Pixel, 176 x 222 bzw. 168). Neues Menü = neue
  Funktion in `CHESTS` eintragen, dann `python tools/generate_icons.py` (schreibt auch die Zeichen nach `UiIcon.java`).
- Im Plugin: `ChestGui.available(plugin, player)` prüfen, dann `ChestGui.enderChestTitle(...)` bzw.
  `ChestGui.bankTitle(...)` als Titel nehmen. Ohne Pack (oder Bedrock) bleibt der bisherige schlichte Titel.
- Die Slot-Positionen ändern sich durch das Design nicht. Wer im Bild Plattenpositionen ändert, muss die Items im
  Plugin passend verschieben.
- Leere Slots mit Füller-Items sind mit `ChestGui.filler()` unsichtbar (`fmc:blank`, nur mit Pack benutzen).
- Erkannt werden die Menüs nicht am Titel: Bank über einen `InventoryHolder`, Endertruhe über `isEcTitle` (Text
  `EC von `, Farbcodes und Schrift-Zeichen werden ignoriert).
- Offen/ungeprüft im Spiel: Offsets (`CHEST_ASCENT = 13`, Titel bei x = 8) und ob die Items sicher vor dem
  Hintergrund liegen. Sitzt das Bild verschoben, nur diese Konstanten in `chest_textures.py` anpassen.

## Wer bekommt das Pack?

- Die Permission heißt **`fmc.resourcepack`** (Standard: niemand). Vergabe über LuckPerms, zum Beispiel:
  ```
  /lp group <teamgruppe> permission set fmc.resourcepack true
  ```
- Das Pack ist **Pflicht** (`resourcepack.force: true`): Wer es ablehnt, wird vom Client getrennt.
  Abschalten: `resourcepack.force: false` in der `config.yml`, danach Plugin-Reload oder Neustart.
- Das Plugin schickt das Pack nur, wenn der Abruf der ZIP beim Start bzw. bei `/fmcpack reload` geklappt hat.
  Ist GitHub nicht erreichbar, wird nichts verschickt, damit kein Ausfall das Team aussperrt.
- Admins (`fmc.resourcepack.admin`) können mit `/fmcpack` arbeiten:

| Befehl | Wirkung |
|---|---|
| `/fmcpack status` | Zeigt URL, Hash, Permission und wie viele Spieler das Pack geladen haben |
| `/fmcpack reload` | ZIP neu abrufen und an berechtigte Spieler schicken |
| `/fmcpack send [Spieler]` | Pack testweise schicken, auch ohne Permission |
| `/fmcpack remove [Spieler]` | Pack wieder entfernen |

Zum Ausprobieren gibt es das Demo-Menü `/fmcmenu` (Permission `fmc.ui.demo`, nur mit geladenem Pack).

## Ohne Server testen

- ZIP lokal bauen: `python tools/build_zip.py` → `dist/FMC-Resourcepack.zip`, in den `resourcepacks`-Ordner von
  Minecraft kopieren und aktivieren.
- Bild des Demo-Menüs zeichnen: `python tools/render_mock.py <pfad-zur-client.jar>` → `dist/mock_fmcmenu.png`.
  Dafür wird einmalig der Minecraft-Client (`client.jar`, 1.21.11) gebraucht. Dessen Schrift wird nur lokal gelesen
  und nicht ins Repo kopiert. Das Bild ist eine Näherung und ersetzt keinen Test im Spiel.

## Fehlersuche

| Problem | Ursache / Lösung |
|---|---|
| Spieler sieht Kästchen statt Icons | Das Pack ist nicht geladen. Hat er die Permission `fmc.resourcepack`? `/fmcpack status` prüfen, notfalls `/fmcpack send <Spieler>`. |
| Nach dem Update ist alles noch beim Alten | `/fmcpack reload` vergessen, oder die Action ist noch nicht fertig (Reiter *Actions*). |
| `/fmcpack reload` meldet „Abruf fehlgeschlagen" | URL falsch, Release fehlt oder GitHub nicht erreichbar. URL im Browser öffnen: sie muss eine ZIP herunterladen. |
| Action ist rot | Log in *Actions* ansehen. Meist fehlt der Ordner `pack/` oder `tools/build_zip.py` hat einen Fehler. |
| Spieler wird beim Join getrennt | Pflicht-Pack abgelehnt oder Download fehlgeschlagen. Er muss „Server-Ressourcenpakete" in den Server-Einstellungen auf *Aktiviert/Nachfragen* stellen. |
| Pack nach Minecraft-Update „inkompatibel" | `pack/pack.mcmeta`: `max_format` (und ggf. `min_format`) anpassen. Aktuell Format 69 bis 75 (Minecraft 1.21.9 bis 1.21.11). |

## Wichtig zu wissen

- Das Pack überschreibt **Vanilla-Texturen** für Buttons, Menü-Hintergründe und Trennlinien. Diese gelten im
  **ganzen Client**, solange das Pack aktiv ist, nicht nur in den FMC-Menüs. Für das Team ist deshalb auch das
  normale Minecraft-Menü dunkel.
- Die Icons liegen in der eigenen Schrift `fmc:icons` (Zeichen ab `U+E000`). Abstände und Balkensegment liegen bei
  `U+F801` bis `U+F810`. Die Rahmenkacheln liegen bei `U+E100` bis `U+E4xx`, die unteren Kacheln mit hochgesetzter
  Randlinie (pixelgenaue Panelhöhe) bei `U+E500` bis `U+E85F`, der Hintergrund der Textbuttons bei `U+E900` bis `U+E902`. Diese Bereiche nicht für anderes benutzen.

## Ordnerstruktur

```
FMC-Resourcepack/
├─ pack/                         ← das eigentliche Resourcepack (wird gezippt)
│  ├─ pack.mcmeta                   Pack-Version
│  ├─ pack.png                      Vorschaubild
│  └─ assets/
│     ├─ fmc/                       eigene Icons (Font fmc:icons) und Balkensegment
│     └─ minecraft/textures/gui/    Buttons, Hintergrund, Trennlinien
├─ tools/
│  ├─ generate_icons.py          ← erzeugt alle PNGs und UiIcon.java
│  ├─ amethyst_theme.py          ← Panel-Themes (Lager, Warp, Farmwelt)
│  ├─ theme_art.py               ← gezeichnete Ersatzbilder für Warp/Farmwelt
│  ├─ ai_art.py                  ← KI-Bilder erzeugen und aufbereiten (art/)
│  ├─ ui_textures.py             ← Buttons, Hintergründe, Trennlinien, Balken
│  ├─ build_zip.py               ← baut dist/FMC-Resourcepack.zip
│  └─ render_mock.py             ← Vorschaubild des Demo-Menüs
├─ .github/workflows/release.yml ← läuft im öffentlichen Repo: baut die ZIP, ersetzt das Release "latest"
└─ dist/                         ← lokale Ausgabe (nicht im Repo)
```
