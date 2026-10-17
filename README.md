# 🎓 Librus Synergia dla Home Assistant

Integracja Home Assistant z dziennikiem **Librus Synergia**: oceny, średnie, frekwencja, terminarz, zadania domowe, wiadomości i plan lekcji w jednym miejscu, razem z gotowymi kartami Lovelace i zdarzeniami do powiadomień na telefon.

> Projekt powstał jako fork [LukMaverick/LibrusSynergiaHA](https://github.com/LukMaverick/LibrusSynergiaHA) i jest rozwijany niezależnie. Dane z Librusa pobiera biblioteka [librus-apix](https://github.com/RustySnek/librus-apix).

## ✨ Co potrafi

| Obszar | Szczegóły |
|--------|-----------|
| 📊 **Oceny** | oceny z podziałem na przedmioty, średnia globalna i średnie z przedmiotów (z wykresami historii) |
| 🕒 **Frekwencja** | procent frekwencji, liczba nieobecności, listy usprawiedliwionych i nieusprawiedliwionych |
| 📅 **Plan lekcji** | dziś, jutro, następna lekcja i cały tydzień, scalone ze sprawdzianami, zadaniami i zastępstwami |
| 🗓️ **Terminarz** | zdarzenia sklasyfikowane według typu (sprawdzian, kartkówka, wycieczka, dzień wolny...) |
| 🏠 **Zadania domowe** | lista z pilnością oraz sensor „do zrobienia na jutro" i „co spakować do plecaka" |
| 📬 **Wiadomości** | nadawca, temat, data i załączniki (treść nie jest pobierana, więc wiadomość nie zostaje oznaczona jako przeczytana) |
| 🔔 **Zdarzenia** | nowa ocena, wiadomość, nieobecność, zadanie i wpis w terminarzu, gotowe do automatyzacji |
| 🧒 **Dwie karty** | `librus-card` (dashboard dziecka) i `librus-terminarz-card` instalują się razem z integracją |
| 👧👦 **Wielu uczniów** | każde dziecko to osobny wpis integracji, a zdarzenia niosą imię ucznia i `entry_id` |

## 📦 Instalacja

### HACS (zalecane)

[![Otwórz w HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mkrzych&repository=LibrusSynergiaHA&category=integration)

Albo ręcznie:

1. HACS → menu ⋮ → **Custom repositories**.
2. URL: `https://github.com/mkrzych/LibrusSynergiaHA` (bez `.git` na końcu), kategoria: **Integration**.
3. Znajdź **Librus Synergia HA**, zainstaluj i zrestartuj Home Assistant.

> Błąd *„is not a valid app repository"* oznacza, że w kroku 2 wybrano złą kategorię (np. AppDaemon). Musi być **Integration**.

### Ręcznie

Skopiuj `custom_components/librus_apix` do katalogu `config/custom_components/` i zrestartuj Home Assistant.

Wymagania: Home Assistant **2024.8.0** lub nowszy.

## ⚙️ Konfiguracja

1. **Ustawienia → Urządzenia i usługi → Dodaj integrację**.
2. Wyszukaj **Librus APIX**.
3. Podaj login i hasło do Librus Synergia.

Dane odświeżają się **co 2 godziny**. Pierwsze uruchomienie tylko zapamiętuje stan, więc nie dostaniesz lawiny powiadomień o starych ocenach. Zapamiętane elementy (oceny, wiadomości, zadania, terminarz, nieobecności) są zapisywane trwale, więc po restarcie Home Assistanta zdarzenia o rzeczach, które pojawiły się w Librusie w czasie przerwy, zostaną wysłane (maksymalnie 20 najnowszych danego rodzaju). Drugie dziecko dodajesz jako kolejny wpis integracji (jeden login = jeden wpis).

## 🧩 Encje

> Identyfikatory powstają z nazw w Librusie. Jeśli Twoje wyglądają inaczej, sprawdź je w **Narzędzia deweloperskie → Stany**.

### Podstawowe

| Sensor | Stan | Uwagi |
|--------|------|-------|
| `sensor.informacje_o_uczniu` | imię i nazwisko | klasa, wychowawca, szkoła w atrybutach |
| `sensor.szczesliwy_numerek` | numer | |
| `sensor.oceny` | liczba ocen | wszystkie oceny bieżącego semestru |
| `sensor.srednia_ocen` | średnia globalna | wykres historii |
| `sensor.<przedmiot>` | lista ocen, np. „4, 3+, 5" | |
| `sensor.srednia_<przedmiot>` | średnia z przedmiotu | wykres historii |
| `sensor.frekwencja` | % frekwencji | atrybuty `semestr_1`, `semestr_2` |
| `sensor.nieobecnosci` | liczba nieobecności | `usprawiedliwione`, `nieusprawiedliwione`, `lista` (ostatnie 30) |
| `sensor.wiadomosci` | liczba nieprzeczytanych | lista wiadomości w atrybutach |
| `sensor.terminarz` | liczba zdarzeń | atrybuty opisane w sekcji `librus-terminarz-card` |
| `sensor.sprawdziany` | sprawdziany i kartkówki w ciągu 7 dni | pod odznaki i automatyzacje |
| `sensor.zadania` | liczba zadań (bez przeterminowanych) | |

### Plan lekcji i zadania (od v1.3.0)

Te sensory mają stałe nazwy `sensor.librus_<imię>_...`, gdzie `<imię>` to imię ucznia (np. `ola`).

| Sensor | Stan | Najważniejsze atrybuty |
|--------|------|------------------------|
| `..._plan_dzis` | zakres godzin („08:00–14:30") lub „Wolne" | `lekcje`, `przedmioty`, `liczba_sprawdzianow`, `wydarzenia_dnia`, `dzien_wolny` |
| `..._plan_jutro` | jak wyżej, dla najbliższego dnia nauki | dodatkowo `data`, `dzien`, `czy_jutro` |
| `..._nastepna_lekcja` | przedmiot trwającej lub najbliższej lekcji | `od`, `do`, `sala`, `nauczyciel`, `trwa`, `sprawdzian` |
| `..._plan_tygodnia` | zakres dat („12.10–18.10") | `dni`, `numery_lekcji`, `godziny`, `entry_id` |
| `..._do_zrobienia_jutro` | liczba zadań i sprawdzianów | `zadania`, `sprawdziany`, `przedmioty_do_spakowania`, `data` |
| `..._zadania_otwarte` | liczba zadań od dziś | `zadania` (z `pilnosc`, `tresc`), `liczba_dzis`, `liczba_jutro`, `po_terminie` |

`plan_tygodnia` pokazuje najbliższy tydzień nauki, a od piątku po ostatniej lekcji (i w weekend) tydzień **następny**. Lekcje mają znaczniki: 📝 sprawdzian, 🏠 zadanie, ⚠ zastępstwo, ❌ odwołanie. Wycieczki, rady pedagogiczne i dni wolne trafiają do `wydarzenia_dnia`.

### Usługa `librus_apix.pobierz_tydzien`

Zwraca plan wybranego tygodnia scalony z terminarzem i zadaniami (`entry_id` znajdziesz w atrybutach `plan_tygodnia`). Bieżący i następny tydzień pochodzą z danych integracji, pozostałe są pobierane z Librusa i trzymane w pamięci przez godzinę. Z usługi korzysta karta przy przełączaniu tygodni.

## 🧒 Karty Lovelace

Obie karty są częścią integracji, więc nie trzeba niczego dodatkowo instalować z HACS. W trybie *storage* integracja sama dodaje je do zasobów dashboardów (po aktualizacji odśwież stronę: Ctrl+Shift+R). W trybie YAML:

```yaml
lovelace:
  resources:
    - url: /librus_apix_static/librus-card.js
      type: module
    - url: /librus_apix_static/librus-terminarz-card.js
      type: module
```

### `librus-card`: dashboard dziecka

Pięć widoków (`widok:`): `dzis`, `jutro`, `tydzien`, `zadania` (kolory pilności) i `plecak` (co spakować plus zadania i sprawdziany na jutro). Widok tygodnia ma strzałki ◀ Teraz ▶ (2 tygodnie wstecz, 4 w przód).

```yaml
type: custom:librus-card
widok: tydzien
slug: ola              # imię z identyfikatorów sensor.librus_ola_*
```

Kilkoro dzieci w jednej karcie (przełącznik zapamiętuje wybór na urządzeniu):

```yaml
type: custom:librus-card
widok: dzis
uczniowie:
  - slug: ola
    nazwa: Ola
    numerek: sensor.szczesliwy_numerek   # opcjonalnie
    numer_w_dzienniku: 7                  # opcjonalnie: podświetla szczęśliwy numerek
  - slug: tomek
przedmioty:                               # opcjonalne nadpisania wyglądu
  Matematyka: { emoji: "🔢", kolor: "210 70% 55%" }
```

### `librus-terminarz-card`

Terminarz pogrupowany po dniach (Dziś / Jutro / Środa, 14 paź), z ikonami typów, wyróżnionymi sprawdzianami, filtrami, podsumowaniem „2 sprawdziany w ciągu 7 dni" i widokiem miesiąca. Ma edytor wizualny.

```yaml
type: custom:librus-terminarz-card
entity: sensor.terminarz       # puste = wykryj automatycznie
tytul: Terminarz
widok: agenda                  # agenda | miesiac
dni: 30                        # horyzont agendy
typy: [sprawdzian, kartkowka]  # opcjonalnie: sprawdzian, kartkowka, dzien_wolny, wycieczka, odwolane, rada, zebranie, inne
filtry: true
kompakt: false                 # jedna linia na zdarzenie
pokaz_opis: true
pokaz_nauczyciela: false
max_zdarzen: 0                 # 0 = bez limitu
```

Jedna karta obsługuje jednego ucznia (jedną encję). Dla kilku dzieci dodaj osobne karty z różnym `entity`.

Atrybuty `sensor.terminarz` (oprócz `zdarzenia`, `liczba_zdarzen`, `typy`): w każdym zdarzeniu `typ`, `ikona`, `wazne`, `dni_do`, `dzien_tygodnia`, `nauczyciel`, `opis`, a na poziomie sensora `typy_zdarzen`, `liczba_sprawdzianow_7_dni`, `najblizszy_sprawdzian`, `zakres_do`.

### Podgląd bez Home Assistanta

W katalogu repozytorium uruchom `python3 -m http.server` i otwórz `/custom_components/librus_apix/frontend/demo.html` lub `demo-terminarz.html`.

### Prostsze karty z wbudowanych elementów

Oceny i średnie:

```yaml
type: entities
title: "📚 Oceny"
entities:
  - sensor.srednia_ocen
  - sensor.oceny
  - sensor.szczesliwy_numerek
```

Średnia z przedmiotu:

```yaml
type: gauge
entity: sensor.srednia_matematyka
name: Matematyka
min: 1
max: 6
severity: { green: 4.5, yellow: 3, red: 0 }
```

Ostatnie wiadomości (markdown, bez dodatkowych kart):

```yaml
type: markdown
title: 📬 Wiadomości
content: >
  {% for w in (state_attr('sensor.wiadomosci', 'wiadomosci') or [])[:5] %}
  {{ '🔴' if w.nieprzeczytana else '⚪' }} **{{ w.temat }}**{{ ' 📎' if w.ma_zalacznik }}
  {{ w.nadawca }} · {{ w.data }}

  {% endfor %}
```

Plan tygodnia jako tabela (plan awaryjny bez karty):

```yaml
type: markdown
content: >
  {% set s = 'sensor.librus_ola_plan_tygodnia' %}
  {% set dni = state_attr(s, 'dni') or [] %}
  ### 📅 {{ states(s) }}
  | Nr |{% for d in dni[:5] %} {{ d.skrot }} {{ d.data[8:] }}.{{ d.data[5:7] }}{{ ' 🎉' if d.dzien_wolny }} |{% endfor %}
  |---|{% for d in dni[:5] %}---|{% endfor %}
  {% for n in state_attr(s, 'numery_lekcji') or [] -%}
  | **{{ n }}** |{% for d in dni[:5] -%}
  {%- set l = d.lekcje | selectattr('numer', 'eq', n) | list | first | default(none) -%}
  {%- if l %} {{ '~~' if l.odwolana }}{{ l.przedmiot[:12] }}{{ '~~ ❌' if l.odwolana }}{{ ' ⚠' if l.zastepstwo }}{{ ' 📝' if l.sprawdzian }}{{ ' 🏠' if l.zadania }}{% endif %} |
  {%- endfor %}
  {% endfor %}
```

## 🔔 Powiadomienia i automatyzacje

Integracja wysyła zdarzenia Home Assistant przy każdym odświeżeniu danych. Możesz je przetestować bez czekania: **Narzędzia deweloperskie → Zdarzenia**, wpisz nazwę zdarzenia i dane, kliknij **Wyślij zdarzenie**.

| Zdarzenie | Dane |
|-----------|------|
| `librus_apix_nowa_ocena` | `przedmiot`, `ocena`, `data`, `kategoria`, `nauczyciel`, `uczen`, `entry_id` |
| `librus_apix_nowa_wiadomosc` | `nadawca`, `temat`, `data`, `ma_zalacznik`, `uczen`, `entry_id` |
| `librus_apix_nowa_nieobecnosc` | `data`, `przedmiot`, `numer_lekcji`, `typ`, `usprawiedliwiona`, `nauczyciel`, `temat` |
| `librus_apix_nowe_zadanie` | `przedmiot`, `kategoria`, `termin`, `nauczyciel`, `uczen`, `entry_id`, a także `id`, `termin_iso`, `dni_do`, `pilnosc`, `tresc`, `dzien_tygodnia_terminu` |
| `librus_apix_nowe_zdarzenie` | `data`, `tytul`, `przedmiot`, `godzina`, `typ`, `wazne`, `uczen`, `entry_id` |

Nieobecność oznacza wpisy `nb` i `u` w dzienniku. Spóźnienia i zwolnienia jej nie wywołują, a samo usprawiedliwienie wcześniejszej nieobecności nie jest nową nieobecnością.

### Nowa ocena (dla wszystkich dzieci)

```yaml
automation:
  - alias: "Librus: nowa ocena"
    trigger:
      platform: event
      event_type: librus_apix_nowa_ocena
    action:
      - service: notify.mobile_app_TWOJ_TELEFON
        data:
          title: "🎓 {{ trigger.event.data.uczen }}: {{ trigger.event.data.ocena }}"
          message: >-
            {{ trigger.event.data.przedmiot }} ({{ trigger.event.data.kategoria }}),
            {{ trigger.event.data.nauczyciel }}
```

Tylko dla jednego dziecka, dodaj warunek:

```yaml
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.uczen == 'Ola Kowalska' }}"
```

### Nowa nieobecność

```yaml
automation:
  - alias: "Librus: nowa nieobecność"
    trigger:
      platform: event
      event_type: librus_apix_nowa_nieobecnosc
    action:
      - service: notify.mobile_app_TWOJ_TELEFON
        data:
          title: "🚫 Librus: nieobecność"
          message: >-
            {{ trigger.event.data.data }}, lekcja {{ trigger.event.data.numer_lekcji }}:
            {{ trigger.event.data.przedmiot }}
            ({{ 'usprawiedliwiona' if trigger.event.data.usprawiedliwiona else 'nieusprawiedliwiona' }})
```

### Nowa wiadomość

```yaml
automation:
  - alias: "Librus: nowa wiadomość"
    trigger:
      platform: event
      event_type: librus_apix_nowa_wiadomosc
    action:
      - service: notify.mobile_app_TWOJ_TELEFON
        data:
          title: "📬 {{ trigger.event.data.nadawca }}"
          message: "{{ trigger.event.data.temat }}"
```

### Wieczorne przypomnienie o plecaku

```yaml
automation:
  - alias: "Librus: spakuj się na jutro"
    trigger:
      - platform: time
        at: "19:00:00"
    condition:
      - condition: template
        value_template: "{{ states('sensor.librus_ola_plan_jutro') != 'Wolne' }}"
    action:
      - service: notify.mobile_app_telefon_oli
        data:
          title: "Plecak na jutro 🎒"
          message: >
            {% set d = 'sensor.librus_ola_do_zrobienia_jutro' %}
            Przedmioty: {{ state_attr(d, 'przedmioty_do_spakowania') | join(', ') }}.
            {% for z in state_attr(d, 'zadania') %}
            🏠 {{ z.przedmiot }}{{ ': ' ~ z.tresc if z.tresc }}
            {% endfor %}
            {% for s in state_attr(d, 'sprawdziany') %}
            📝 {{ s.tytul }} {{ s.przedmiot }}
            {% endfor %}
```

### Dzień przed sprawdzianem

```yaml
automation:
  - alias: "Librus: jutro sprawdzian"
    trigger:
      - platform: time
        at: "18:00:00"
    condition:
      - condition: template
        value_template: "{{ state_attr('sensor.terminarz', 'najblizszy_sprawdzian').dni_do == 1 }}"
    action:
      - service: notify.mobile_app_TWOJ_TELEFON
        data:
          message: "Jutro sprawdzian: {{ state_attr('sensor.terminarz', 'najblizszy_sprawdzian').przedmiot }}"
```

> Nazwę telefonu znajdziesz w **Ustawienia → Urządzenia i usługi → Mobile App** (np. `notify.mobile_app_samsung_galaxy_s24`).

## 🩺 Rozwiązywanie problemów

**Włączenie logów debug** (`configuration.yaml`):

```yaml
logger:
  logs:
    custom_components.librus_apix: debug
```

**Błąd logowania.** Sprawdź login i hasło w przeglądarce. Po zmianach po stronie Librusa może być potrzebna nowsza wersja `librus-apix`. Integracja wymaga `>=1.5.2`.

**Nie widzę encji.** Szukaj po części nazwy w **Narzędzia deweloperskie → Stany**. Nazwy zależą od języka i danych w dzienniku.

**Karta się nie ładuje.** Odśwież stronę z pominięciem pamięci podręcznej (Ctrl+Shift+R) i sprawdź, czy zasób `/librus_apix_static/...` jest na liście zasobów dashboardu.

**Zgłaszanie błędów.** Otwórz [issue](https://github.com/mkrzych/LibrusSynergiaHA/issues) z opisem problemu, krokami do odtworzenia i logami (usuń dane osobowe!).

## 🛠️ Rozwój

```bash
git clone https://github.com/mkrzych/LibrusSynergiaHA
cd LibrusSynergiaHA

# środowisko testowe z Home Assistantem i Code Server
docker-compose up -d
# Home Assistant: http://localhost:8123, Code Server: http://localhost:8443

# testy logiki (z atrapami HA)
pip install -r requirements_test.txt
pytest tests/
```

W CI działają trzy workflowy: testy (`tests.yml`), `hassfest` oraz walidacja HACS (`validate.yml`). Pull requesty są mile widziane.

## 🛡️ Bezpieczeństwo i prywatność

- Dane logowania trafiają do magazynu Home Assistant na Twoim serwerze i nigdzie poza Librus nie są wysyłane. Home Assistant nie szyfruje ich w konfiguracji, więc zabezpiecz kopie zapasowe i dostęp do `.storage`.
- Biblioteka `librus-apix` korzysta z portalu Librus Synergia. Nie jest to oficjalne API, więc zmiany po stronie Librusa mogą chwilowo psuć integrację.
- `visible: - user: <id dziecka>` w widoku dashboardu ukrywa tylko zakładkę i **nie jest kontrolą dostępu**. Konto dziecka z dostępem do HA może odczytać wszystkie encje (także wiadomości) przez narzędzia deweloperskie lub API. Nie umieszczaj wiadomości na dashboardzie dziecka, a jeśli to ważne, ogranicz uprawnienia jego konta.
- Treść wiadomości nie jest pobierana, żeby nie oznaczać ich jako przeczytanych w Librusie.

## 📄 Licencja i pochodzenie

Licencja [MIT](LICENSE). Projekt rozwija [Marcin Krzych](https://github.com/mkrzych) jako fork [LukMaverick/LibrusSynergiaHA](https://github.com/LukMaverick/LibrusSynergiaHA) (MIT). Dane z Librusa pobiera [librus-apix](https://github.com/RustySnek/librus-apix) autorstwa RustySnek.

Projekt nie jest związany z firmą Librus ani przez nią wspierany.
