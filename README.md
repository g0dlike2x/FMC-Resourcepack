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

## Menüs mit Hintergrund-Panel (wie im Vorbild)

Das Panel (Rahmen, rote Linie, Profilkarte) ist ein **einzelnes großes Zeichen** der Schrift (`UiIcon.PANEL`). Es steht in
der ersten Textzeile eines Dialogs und ragt nach unten über die weiteren Zeilen und die echten Buttons hinaus. Texte
liegen darüber und werden mit `UiLine` pixelgenau platziert:

```java
Component line = UiLine.create()
    .to(UiIcon.NAME_X).text(name, NamedTextColor.WHITE, true)        // links, fett
    .right(UiIcon.TEXT_RIGHT, UiLine.create().text("12.500", NamedTextColor.YELLOW, false)
        .gap(2).icon(UiIcon.TOKENS))                                   // rechtsbündig
    .build(UiIcon.PANEL_WIDTH);                                        // alle Zeilen gleich breit
```

- Alle Zeilen müssen **dieselbe Gesamtbreite** haben (`build(UiIcon.PANEL_WIDTH)`), sonst zentriert Minecraft sie
  unterschiedlich und der Text verrutscht. Eine Zeile ist 9 Pixel hoch.
- Die Breiten kommen aus `FontMetrics.java` (Minecraft-Schrift) und `UiIcon.advance()` (Icons). Beide Dateien werden
  erzeugt: `generate_icons.py` für die Icons, `python tools/gen_font_widths.py <client.jar>` für die Schrift. Das
  Skript für die Schrift muss nur nach einem Minecraft-Update mit geänderter Schrift neu laufen.
- Das Panel und die Karte sind in `make_panel()` in `generate_icons.py` gezeichnet (Maße oben im Abschnitt „Panel“).
  Ändert man die Zeilenhöhe oder die Position der Karte, müssen die Werte `CARD`, `STAR_BOX`, `NAME_X` dort und die
  Zeilen im Menü (`FmcMenuCommand`) zusammenpassen.

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
  `U+F801` bis `U+F810`. Diese Bereiche nicht für anderes benutzen.

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
│  ├─ ui_textures.py             ← Buttons, Hintergründe, Trennlinien, Balken
│  ├─ build_zip.py               ← baut dist/FMC-Resourcepack.zip
│  └─ render_mock.py             ← Vorschaubild des Demo-Menüs
├─ .github/workflows/release.yml ← läuft im öffentlichen Repo: baut die ZIP, ersetzt das Release "latest"
└─ dist/                         ← lokale Ausgabe (nicht im Repo)
```
