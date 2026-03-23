# Stripe-Billing-Alternativen für kleine europäische SaaS

**Paddle ist der stärkste Gesamtkandidat** für ein europäisches SaaS-Projekt mit 100 Abonnenten à 100 €/Monat – dank vollständiger Steuerabwicklung (Merchant of Record), offiziellem Python-SDK und EUR-Auszahlungen ohne Aufpreis. Die günstigste Variante bleibt allerdings **Chargebee** im kostenlosen Starter-Plan kombiniert mit Stripe als Zahlungsgateway, sofern man die EU-VAT-Pflichten selbst übernimmt. Die Entscheidung hängt letztlich an einer Kernfrage: **Steuerliche Komplexität auslagern (MoR) oder Kosten minimieren (Billing-Plattform + eigene VAT-Compliance)?**

Im Folgenden werden alle relevanten Anbieter systematisch verglichen – mit konkreten Kosten bei 10.000 €/Monat Umsatz, SDK-Qualität, MoR-Status und einer abschließenden Empfehlung.

---

## Die Kostenlandschaft auf einen Blick

| Anbieter | Effektive Monatskosten | MoR? | Python-SDK | Eignung |
|---|---|---|---|---|
| **Chargebee** (Starter + Stripe) | ~€175 | ❌ | ⭐⭐⭐⭐⭐ | ★★★★★ |
| **Stripe Billing** (Referenz) | ~€235–285 | ❌ | ⭐⭐⭐⭐⭐ | ★★★★☆ |
| **Braintree** (nur Payment) | ~€213 | ❌ | ⭐⭐⭐⭐ | ★★☆☆☆ |
| **Paddle** | ~€546 | ✅ | ⭐⭐⭐⭐⭐ | ★★★★★ |
| **2Checkout 2Subscribe** | ~€495 | ❌ | ⭐⭐ | ★★★☆☆ |
| **Lemon Squeezy** | ~€696 | ✅ | ⭐⭐ | ★★★☆☆ |
| **2Checkout 2Monetize** | ~€660 | ✅ | ⭐⭐ | ★★☆☆☆ |
| **FastSpring** | ~€678 (geschätzt) | ✅ | ⭐ | ★★☆☆☆ |
| **Recurly** | ~€405 | ❌ | ⭐⭐⭐⭐ | ★★☆☆☆ |
| **Lago** (self-hosted) | ~€30–50 Infra | ❌ | ⭐⭐⭐⭐ | ★★☆☆☆ |
| **Stigg / Orb / Kill Bill** | variabel | ❌ | variabel | ★☆☆☆☆ |

*Kosten bei 100 Transaktionen à 100 €/Monat. Bei Nicht-MoR-Anbietern zzgl. Steuerberater-/Filing-Kosten (€50–200/Monat).*

---

## Merchant-of-Record-Anbieter: Steuerfreiheit hat ihren Preis

Ein Merchant of Record (MoR) tritt als rechtlicher Verkäufer gegenüber dem Endkunden auf. Das bedeutet: **VAT-Registrierung, -Berechnung, -Einzug, -Meldung und -Abführung in allen Ländern entfallen komplett** für den SaaS-Betreiber. Für ein europäisches Unternehmen, das B2C-Digital-Services in die gesamte EU verkauft, kann dies enormen Verwaltungsaufwand eliminieren.

**Paddle** ist unter den MoR-Anbietern der klare Favorit für dieses Szenario. Die Gebührenstruktur liegt bei **5 % + 0,50 $ pro Transaktion** – all-inclusive, ohne Aufschläge für internationale Zahlungen oder Währungsumrechnung. Bei 10.000 €/Monat ergibt das rund **€546 monatlich** (effektiv ~5,5 %). Paddle sitzt in London, zahlt per SEPA ohne Zusatzkosten in EUR aus und bietet ein offizielles Python-SDK (`paddle-python-sdk` auf PyPI) mit Flask/Django-Support und Webhook-Verifikation. Die inkludierten **ProfitWell Metrics** liefern kostenlose SaaS-Analytics (MRR, Churn, LTV), und **Paddle Retain** optimiert die Dunning-Logik zur Churn-Reduktion. Nachteile: Auszahlungen erfolgen nur monatlich (Saldo am 1., Überweisung bis zum 15.), die Checkout-Anpassung ist eingeschränkt, und auf dem Kontoauszug des Kunden erscheint „Paddle" statt der eigenen Marke.

**Lemon Squeezy** bietet zwar dasselbe Basispreismodell (5 % + 0,50 $), erhebt jedoch einen **zusätzlichen Aufschlag von 1,5 % für nicht-US-Transaktionen**. Da ein europäisches SaaS praktisch ausschließlich solche Transaktionen generiert, steigt die effektive Rate auf **~7 % (~€696/Monat)**. Schwerer wiegt: Alle Zahlungen werden in USD abgewickelt, Auszahlungen erfolgen nur in USD, und es existiert **kein offizielles Python-SDK**. Nach der Übernahme durch Stripe im Juli 2024 berichten Nutzer zudem von Instabilitäten (500-Fehler, verzögerte Auszahlungen). Für europäische SaaS-Projekte ist Lemon Squeezy daher klar hinter Paddle einzuordnen.

**FastSpring** veröffentlicht keine Preise – Berichte deuten auf **~5,9 % + 0,95 $ pro Transaktion** hin (~€678/Monat). Das Unternehmen ist seit 2005 am Markt und deckt über 200 Steuerregionen ab, richtet sich aber deutlich an **mittelgroße bis große Unternehmen**. Es gibt kein Python-SDK, die API-Dokumentation wirkt veraltet, und das Vertragsmodell mit Pflicht-Vertriebskontakt passt schlecht zu einem kleinen SaaS.

**2Checkout/Verifone** bietet MoR nur im teuersten Plan „2Monetize" an: **6 % + 0,60 $ pro Transaktion (~€660/Monat)**. Der günstigere „2Subscribe"-Plan (4,5 % + 0,45 $, ~€495/Monat) beinhaltet zwar Subscription-Management, aber keine Steuerabwicklung. Auch hier fehlt ein Python-SDK, und die Markenverwirrung (2Checkout → Verifone) sowie Nutzerberichte über verzögerte Auszahlungen und einen 5 %-Rolling-Reserve für 90 Tage sprechen gegen die Plattform.

---

## Billing-Plattformen ohne MoR: Günstiger, aber mit Steuerpflicht

**Chargebee** ist die attraktivste Option in dieser Kategorie. Der **Starter-Plan ist kostenlos** bis zu einem kumulierten Abrechnungsvolumen von 250.000 $ – bei 10.000 €/Monat reicht das für **knapp zwei Jahre**. Danach fallen 0,75 % Overage-Gebühr an. Da Chargebee selbst keine Zahlungen verarbeitet, braucht man ein Gateway wie Stripe (1,4 % + €0,25 für EEA-Karten). **Gesamtkosten in den ersten ~2 Jahren: nur ~€175/Monat** (reine Gateway-Gebühren). Das Python-SDK (`chargebee` auf PyPI, v3.17, ~73.000 wöchentliche Downloads) bietet Async-Support, Type Annotations und eine „Time Machine" für Testabrechnungen. Chargebee berechnet EU-VAT automatisch, validiert VAT-IDs über VIES und generiert EU-konforme Rechnungen – **die Meldung und Abführung bleibt aber beim Betreiber**. Für ein kleines SaaS mit einfachem Pricing ist Chargebee + Stripe die kostengünstigste professionelle Lösung.

**Stripe Billing** selbst kostet seit der Preiserhöhung Mitte 2024 einheitlich **0,7 % des Billing-Volumens** (zuvor 0,5 % im Starter-Plan). Zusammen mit den Zahlungsgebühren (1,4 % + €0,25 für EEA-Karten) und optionalem Stripe Tax (0,5 %) ergeben sich **€235–285/Monat** (2,35–2,85 %). Das `stripe`-Python-Paket (v14.x, MIT-Lizenz) ist branchenführend: vollständige Typisierung, Async-Support, umfassende Dokumentation mit Code-Beispielen. Das Customer Portal, Smart Retries (56 % Recovery-Rate bei fehlgeschlagenen Zahlungen) und die nahtlose Tax-Integration machen Stripe Billing zum Goldstandard bei Developer Experience. Der zentrale Nachteil: **Stripe Tax berechnet und erhebt Steuern, meldet und zahlt sie aber nicht** – ein Steuerberater oder Filing-Partner (Taxually, Marosa; ca. €50–200/Monat) ist zusätzlich nötig.

**Recurly** positioniert sich mit ML-gesteuertem Dunning als Premium-Option, kostet aber **~€405/Monat** (Plattform ~€230 + Gateway ~€175) und hat seit 2025 ein Mindest-TPV von 1 Mio. $ auf der Preisseite. Für 100 Subscriber mit einfachem Pricing ist das deutlich überdimensioniert und zu teuer. Das Python-SDK ist solide, aber Webhooks kommen noch im XML-Format.

**Braintree** (PayPal) bietet die niedrigsten reinen Transaktionsgebühren in Europa: **1,9 % + €0,23 (~€213/Monat)**. Allerdings ist es ein reiner Payment-Processor mit nur rudimentärem Subscription-Management – kein Dunning, kein Kundenportal, keine Rechnungserstellung, **keinerlei Steuerberechnung**. Man müsste fast die gesamte Billing-Logik selbst bauen oder Braintree mit Chargebee kombinieren. Als Stand-alone-Lösung für Subscriptions nicht empfehlenswert.

---

## Open-Source und Nischentools: Meist Overkill für 100 Subscriber

**Lago** (getlago.com, Paris) ist die vielversprechendste Open-Source-Alternative. Self-Hosted unter AGPL v3 kostenlos, mit offiziellem Python-SDK (`lago-python-client`) und modernem Stack (httpx, pydantic). Lago glänzt bei Usage-Based-Billing und Hybrid-Modellen. Für **100 Subscriber mit einem fixen Monatsbeitrag** ist die Self-Hosting-Last jedoch unverhältnismäßig: Docker, PostgreSQL, Redis, ClickHouse und Worker-Prozesse müssen betrieben werden. Das Kundenportal ist nur im kostenpflichtigen Cloud-Plan verfügbar. **Empfehlung: Nur sinnvoll, wenn künftig nutzungsbasierte Abrechnung geplant ist.**

**Kill Bill** (Apache 2.0) ist ein ausgereiftes Billing-Framework, das jedoch auf Java basiert – ein erheblicher Stack-Mismatch mit einem Python-Backend. Das Python-SDK ist auto-generiert und veraltet. Die Einrichtungskomplexität und der JVM-Ressourcenbedarf machen es für kleine Teams unpraktisch.

**Stigg** ist kein Billing-System, sondern eine Pricing-/Packaging-Middleware, die **zusätzlich** zu einem Billing-Provider wie Stripe läuft (~$200–400/Monat extra). Bei einem einzigen fixen Plan löst Stigg ein Problem, das nicht existiert. **Orb** ist auf Usage-Based-Billing für AI/SaaS-Unternehmen spezialisiert und mit geschätzten $500–1.500/Monat Mindestkosten für dieses Szenario irrelevant.

---

## Die entscheidende Abwägung: MoR-Komfort vs. Kosteneffizienz

Die Wahl zwischen MoR und Nicht-MoR ist die strategisch wichtigste Entscheidung. Konkret gerechnet:

**Pfad 1 – Chargebee + Stripe (kein MoR):** ~€175/Monat (erste 2 Jahre) + Filing-Partner ~€100/Monat = **~€275/Monat**. Man muss sich einmalig für VAT-OSS registrieren und quartalsweise eine Meldung abgeben (oder an einen Steuerberater delegieren). Das ist machbar, erfordert aber initiales Setup und laufende Aufmerksamkeit.

**Pfad 2 – Stripe Billing + Tax (kein MoR):** ~€285/Monat + Filing-Partner ~€100/Monat = **~€385/Monat**. Ähnlich wie Pfad 1, aber alles in einem Ökosystem. Weniger Integrationsaufwand als Chargebee + Stripe separat.

**Pfad 3 – Paddle (MoR):** ~€546/Monat, **keine weitere Steuerarbeit nötig**. Rund €160–270 teurer als die Nicht-MoR-Pfade, aber der Zeitaufwand für VAT-Compliance fällt komplett weg. Bei einem Stundensatz von 80–100 € für Gründerzeit amortisiert sich das schnell, wenn VAT-Management mehr als 2–3 Stunden pro Monat kostet.

---

## Ranking und Empfehlung für das konkrete Projekt

**Rang 1 – Paddle** (MoR-Empfehlung): Bestes Gesamtpaket für ein europäisches SaaS. Vollständige Steuerentlastung, offizielles Python-SDK, EUR-SEPA-Auszahlung, inkludierte Analytics und Churn-Prevention. Die Mehrkosten gegenüber Stripe (~€260/Monat) sind der Preis für null steuerlichen Verwaltungsaufwand. Ideal für Solo-Gründer oder kleine Teams, die sich auf das Produkt konzentrieren wollen.

**Rang 2 – Chargebee Starter + Stripe** (Budget-Empfehlung): Die günstigste professionelle Lösung – rund **€175/Monat** für fast zwei Jahre. Hervorragendes Python-SDK, vollständiges Subscription-Management, EU-VAT-Berechnung inklusive. Erfordert eigene VAT-OSS-Registrierung und quartalsweise Filing, was aber mit einem Steuerberater oder Tool wie Taxually gut handhabbar ist.

**Rang 3 – Stripe Billing**: Der Industriestandard mit bestem Developer-Tooling. Bei €235–285/Monat (ohne Tax-Filing) etwas teurer als Chargebee-Starter, aber mit weniger beweglichen Teilen. Sinnvoll, wenn man bereits Stripe nutzt und keine zweite Plattform integrieren möchte.

**Rang 4 – 2Checkout 2Monetize**: Alternative MoR-Option, aber teurer als Paddle (€660 vs. €546/Monat), ohne Python-SDK und mit schwächerer Developer Experience. Nur interessant, wenn Paddle aus einem bestimmten Grund nicht in Frage kommt.

**Nicht empfohlen** für dieses Szenario: Lemon Squeezy (zu teuer für EU, kein Python-SDK, instabil), FastSpring (Enterprise-fokussiert, intransparent), Recurly (zu teuer), Braintree (zu wenig Features), Lago/Kill Bill (zu viel Ops-Aufwand für 100 Subscriber), Stigg/Orb (falscher Use Case).

## Fazit

Für ein europäisches SaaS-Produkt mit 100 Subscribern und einfachem Pricing verdient **Paddle** den Vorzug, wenn man den Steueraufwand komplett eliminieren will – zu einem fairen Preis von rund 5,5 % des Umsatzes. Wer bereit ist, die EU-VAT-Compliance selbst zu managen (oder zu delegieren), fährt mit **Chargebee + Stripe** am günstigsten: effektiv unter 2 % reine Plattform- und Zahlungskosten. Die oft zitierten Open-Source-Alternativen (Lago, Kill Bill) sind bei dieser Projektgröße kein sinnvoller Trade-off – der Betriebsaufwand übersteigt die Ersparnis deutlich. Entscheidend ist: **Bei 10.000 € Monatsumsatz liegt die Kostendifferenz zwischen der günstigsten und teuersten sinnvollen Option bei rund 370 €/Monat** – ein Betrag, der gegen den Wert der eigenen Zeit für Steuer-Compliance und Integrationsaufwand abgewogen werden sollte.