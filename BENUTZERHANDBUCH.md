# Benutzerhandbuch

**KI-gestützter Kostenvoranschlags-Generator für Malerbetriebe**

**Version:** 1.0  
**Erstellt am:** 4. Juni 2025  
**Autor:** Manus AI

---

## Willkommen

Herzlich willkommen beim KI-gestützten Kostenvoranschlags-Generator für Malerbetriebe! Dieses innovative System wurde speziell entwickelt, um Ihnen als Maler oder Malerbetrieb die Erstellung professioneller Kostenvoranschläge zu erleichtern und zu beschleunigen. Mit modernster KI-Technologie können Sie in wenigen Minuten detaillierte, professionelle Angebote erstellen, die Ihre Kunden beeindrucken werden.

## Erste Schritte

### Registrierung und Anmeldung

Der erste Schritt zur Nutzung des Systems ist die Erstellung eines Benutzerkontos. Klicken Sie auf der Startseite auf "Registrieren" und geben Sie Ihre grundlegenden Informationen ein. Sie benötigen eine gültige E-Mail-Adresse, einen Benutzernamen und ein sicheres Passwort. Optional können Sie bereits bei der Registrierung Ihre Firmeninformationen hinterlegen, was später die Angebotserstellung beschleunigt.

Nach der erfolgreichen Registrierung erhalten Sie eine Bestätigungs-E-Mail. Klicken Sie auf den Bestätigungslink, um Ihr Konto zu aktivieren. Anschließend können Sie sich mit Ihren Zugangsdaten anmelden und das System nutzen.

### Dashboard-Übersicht

Nach der Anmeldung gelangen Sie zum Dashboard, Ihrer zentralen Schaltstelle. Hier sehen Sie auf einen Blick alle wichtigen Informationen: Ihre aktuellen Angebote, den Status Ihres Kontingents (bei kostenlosen Konten), Gesamtumsätze und schnelle Aktionen für häufige Aufgaben.

Das Dashboard ist in mehrere Bereiche unterteilt: Der Kopfbereich zeigt Ihre Kontingent-Informationen und bietet schnellen Zugang zu neuen Angeboten. Der Hauptbereich präsentiert Statistiken und eine Übersicht Ihrer letzten Angebote. Die Seitenleiste ermöglicht die Navigation zu verschiedenen Funktionen des Systems.

## Angebotserstellung

### Grundinformationen eingeben

Die Erstellung eines neuen Angebots beginnt mit dem Klick auf "Neues Angebot" im Dashboard oder in der Navigation. Sie gelangen zu einem mehrstufigen Assistenten, der Sie durch den gesamten Prozess führt.

Im ersten Schritt geben Sie die Grundinformationen zum Projekt ein. Dazu gehören der Kundenname (Pflichtfeld), optional die E-Mail-Adresse und Telefonnummer des Kunden, sowie die Projektadresse. Der Projekttitel sollte prägnant das Vorhaben beschreiben, beispielsweise "Wohnzimmer streichen" oder "Fassadenrenovierung Einfamilienhaus".

Besonders wichtig ist die Projektbeschreibung. Hier können Sie in natürlicher Sprache beschreiben, was gemacht werden soll. Das System versteht Eingaben wie "Wohnzimmer, 25 Quadratmeter, weiß streichen, inklusive Grundierung, geschätzt 10 Stunden Arbeit". Je detaillierter Ihre Beschreibung, desto präziser kann die KI das Angebot erstellen.

### Dokumenten-Upload und KI-Analyse

Im zweiten Schritt haben Sie die Möglichkeit, Dokumente hochzuladen, die das System automatisch analysiert. Unterstützt werden Baupläne (PDF, JPG, PNG), Fotos der zu bearbeitenden Räume, bestehende Leistungsverzeichnisse und handschriftliche Notizen oder Skizzen.

Die KI analysiert hochgeladene Dokumente automatisch und extrahiert relevante Informationen wie Raumgrößen, Wandflächen, besondere Anforderungen und bereits vorhandene Materialangaben. Bei Bauplänen erkennt das System Maße und berechnet automatisch die zu streichenden Flächen. Fotos werden auf Oberflächenbeschaffenheit, Farben und Zustand analysiert.

Nach dem Upload sehen Sie eine Vorschau der extrahierten Informationen. Sie können diese überprüfen und bei Bedarf korrigieren. Das System lernt aus Ihren Korrekturen und wird mit der Zeit immer präziser.

### KI-gestützte Angebotsgenerierung

Basierend auf Ihren Eingaben und den analysierten Dokumenten generiert die KI einen ersten Angebotsentwurf. Dieser Prozess dauert normalerweise nur wenige Sekunden. Das System erstellt automatisch einzelne Positionen mit Beschreibungen, Mengen, Einheiten und Preisen.

Falls die KI zusätzliche Informationen benötigt, stellt sie gezielte Rückfragen. Diese können sich auf fehlende Maße, spezielle Anforderungen oder Materialwünsche beziehen. Beantworten Sie diese Fragen so präzise wie möglich, um ein optimales Ergebnis zu erhalten.

Die generierten Positionen basieren auf branchenüblichen Standards und aktuellen Marktpreisen. Sie können alle Positionen individuell anpassen, neue hinzufügen oder bestehende löschen. Das System berechnet automatisch Zwischensummen, Mehrwertsteuer und Gesamtbetrag.

### Angebots-Überprüfung und Anpassung

Bevor Sie das Angebot finalisieren, haben Sie die Möglichkeit zur detaillierten Überprüfung. Kontrollieren Sie alle Positionen auf Vollständigkeit und Richtigkeit. Achten Sie besonders auf Mengenangaben, Preise und Beschreibungen.

Sie können Positionen bearbeiten, indem Sie auf das Stift-Symbol klicken. Ändern Sie Beschreibungen, Mengen oder Preise nach Ihren Anforderungen. Das System aktualisiert automatisch alle abhängigen Berechnungen.

Für wiederkehrende Arbeiten können Sie Positionen als Vorlagen speichern. Diese stehen Ihnen bei zukünftigen Angeboten zur Verfügung und beschleunigen den Erstellungsprozess erheblich.

## PDF-Generierung und Versand

### Professionelle PDF-Erstellung

Sobald Sie mit dem Angebot zufrieden sind, können Sie ein professionelles PDF generieren. Klicken Sie auf "PDF erstellen" und das System generiert automatisch ein formatiertes Dokument mit Ihrem Firmenlogo, allen Angebotspositionen und rechtlichen Hinweisen.

Das PDF enthält alle wichtigen Informationen: Ihre Firmendaten, Kundendaten, eine detaillierte Aufstellung aller Positionen mit Preisen, Zwischensumme, Mehrwertsteuer und Gesamtbetrag. Zusätzlich werden Zahlungsbedingungen, Gewährleistungshinweise und die Gültigkeitsdauer des Angebots aufgeführt.

Die PDF-Generierung erfolgt über zwei Systeme: Primär wird die CraftMyPDF-API verwendet, die hochwertige, professionell formatierte Dokumente erstellt. Als Fallback steht ein lokales System zur Verfügung, das auch bei Ausfall der externen API funktioniert.

### E-Mail-Versand

Das fertige PDF kann direkt aus dem System per E-Mail an den Kunden versendet werden. Klicken Sie auf "Per E-Mail senden" und das System erstellt automatisch eine professionelle E-Mail mit dem PDF als Anhang.

Die E-Mail enthält eine höfliche Anrede, eine kurze Projektbeschreibung, wichtige Eckdaten des Angebots und Ihre Kontaktdaten. Der Text ist professionell formuliert und kann bei Bedarf angepasst werden.

Nach dem Versand wird der Status des Angebots automatisch auf "Versendet" gesetzt und das Versanddatum gespeichert. Sie behalten so immer den Überblick über den Status Ihrer Angebote.

## Angebotsverwaltung

### Angebots-Übersicht

Alle Ihre Angebote finden Sie in der Angebots-Übersicht, die über die Navigation erreichbar ist. Hier sehen Sie eine tabellarische Auflistung aller Angebote mit wichtigen Informationen wie Angebotsnummer, Kunde, Projekt, Betrag und Status.

Sie können die Liste nach verschiedenen Kriterien filtern: Status (Entwurf, Versendet, Angenommen, Abgelehnt), Zeitraum, Kunde oder Projekttyp. Eine Suchfunktion ermöglicht das schnelle Auffinden spezifischer Angebote.

Durch Klick auf ein Angebot gelangen Sie zur Detailansicht, wo Sie alle Informationen einsehen, das Angebot bearbeiten oder erneut versenden können.

### Status-Verwaltung

Jedes Angebot durchläuft verschiedene Status-Stufen: "Entwurf" für noch nicht fertiggestellte Angebote, "Versendet" nach dem E-Mail-Versand, "Angenommen" bei Auftragserteilung und "Abgelehnt" bei Absagen.

Sie können den Status manuell ändern, um den aktuellen Stand zu dokumentieren. Dies hilft bei der Nachverfolgung und Erfolgsanalyse Ihrer Angebote.

### Angebots-Duplikation

Für ähnliche Projekte können Sie bestehende Angebote duplizieren. Klicken Sie auf "Duplizieren" und das System erstellt eine Kopie mit allen Positionen. Sie müssen nur die Kundendaten und projektspezifische Details anpassen.

Diese Funktion ist besonders nützlich für Standardarbeiten oder wenn Sie für denselben Kunden mehrere ähnliche Projekte bearbeiten.

## Kontingent und Abonnements

### Kostenloses Kontingent

Neue Benutzer erhalten drei kostenlose Angebote pro Monat. Dieses Kontingent wird am ersten Tag jedes Monats zurückgesetzt. Im Dashboard sehen Sie jederzeit, wie viele kostenlose Angebote Sie bereits verwendet haben.

Das kostenlose Kontingent umfasst alle Funktionen des Systems: KI-Analyse, PDF-Generierung, E-Mail-Versand und Angebotsverwaltung. Es gibt keine Einschränkungen in der Qualität oder den verfügbaren Features.

### Premium-Abonnement

Für Betriebe mit höherem Bedarf steht ein Premium-Abonnement zur Verfügung. Premium-Nutzer können unbegrenzt viele Angebote erstellen und erhalten zusätzliche Features wie erweiterte Anpassungsmöglichkeiten, Prioritäts-Support und Datenexport-Funktionen.

Das Premium-Abonnement kostet 29,99 Euro pro Monat und kann jederzeit gekündigt werden. Die Abrechnung erfolgt über Stripe, einen sicheren und zuverlässigen Payment-Provider.

### Zusätzliche Angebote

Als Alternative zum Premium-Abonnement können Sie zusätzliche Angebote einzeln kaufen. Ein Paket mit 10 zusätzlichen Angeboten kostet 19,99 Euro und ist unbegrenzt gültig.

Diese Option eignet sich für Betriebe mit unregelmäßigem Bedarf oder für die Überbrückung bis zum nächsten Monat.

## Tipps für optimale Ergebnisse

### Präzise Beschreibungen

Je detaillierter Sie Ihre Projekte beschreiben, desto genauer werden die KI-generierten Angebote. Geben Sie immer Raumgrößen, gewünschte Farben, Oberflächenbeschaffenheit und besondere Anforderungen an.

Verwenden Sie Fachbegriffe, die das System versteht: "Grundierung", "Zwischenanstrich", "Schlussanstrich", "Spachteln", "Abkleben". Das System ist auf die Malerbranche spezialisiert und versteht branchenspezifische Begriffe.

### Qualitätsfotos

Beim Upload von Fotos achten Sie auf gute Beleuchtung und scharfe Bilder. Fotografieren Sie alle zu bearbeitenden Flächen aus verschiedenen Winkeln. Besonders wichtig sind Detailaufnahmen von problematischen Bereichen wie Rissen, Flecken oder besonderen Oberflächenstrukturen.

### Regelmäßige Preisanpassung

Überprüfen Sie regelmäßig die vom System vorgeschlagenen Preise und passen Sie diese an Ihre lokalen Gegebenheiten an. Das System lernt aus Ihren Anpassungen und wird mit der Zeit immer präziser.

Speichern Sie häufig verwendete Positionen als Vorlagen mit Ihren individuellen Preisen. Dies beschleunigt zukünftige Angebotserstellungen erheblich.

## Fehlerbehebung

### Häufige Probleme

**PDF-Generierung schlägt fehl:** Überprüfen Sie Ihre Internetverbindung und versuchen Sie es erneut. Das System wechselt automatisch auf lokale Generierung, falls die externe API nicht verfügbar ist.

**E-Mail-Versand funktioniert nicht:** Kontrollieren Sie die E-Mail-Adresse des Kunden auf Tippfehler. Bei wiederholten Problemen wenden Sie sich an den Support.

**KI-Analyse liefert unplausible Ergebnisse:** Überprüfen Sie Ihre Eingaben auf Vollständigkeit und Klarheit. Verwenden Sie präzise Beschreibungen und eindeutige Maßangaben.

### Support kontaktieren

Bei Problemen oder Fragen steht Ihnen unser Support-Team zur Verfügung. Premium-Kunden erhalten Prioritäts-Support mit garantierten Antwortzeiten.

Kontaktieren Sie uns über das Kontaktformular im System oder per E-Mail. Beschreiben Sie Ihr Problem so detailliert wie möglich und fügen Sie Screenshots bei, falls relevant.

## Datenschutz und Sicherheit

### Datenschutz

Alle Ihre Daten werden verschlüsselt gespeichert und niemals an Dritte weitergegeben. Kundendaten werden nur für die Angebotserstellung verwendet und können jederzeit gelöscht werden.

Das System ist DSGVO-konform und erfüllt alle deutschen Datenschutzbestimmungen. Sie haben jederzeit das Recht auf Auskunft, Berichtigung oder Löschung Ihrer Daten.

### Sicherheit

Die Übertragung aller Daten erfolgt verschlüsselt über HTTPS. Passwörter werden mit modernen Hashing-Verfahren gespeichert und sind für niemanden einsehbar.

Verwenden Sie ein starkes Passwort und loggen Sie sich nach der Nutzung aus, besonders an öffentlichen Computern. Aktivieren Sie die Zwei-Faktor-Authentifizierung für zusätzliche Sicherheit.

## Fazit

Der KI-gestützte Kostenvoranschlags-Generator revolutioniert die Art, wie Malerbetriebe Angebote erstellen. Mit modernster Technologie, benutzerfreundlicher Bedienung und professionellen Ergebnissen sparen Sie Zeit und beeindrucken Ihre Kunden.

Nutzen Sie die kostenlosen Angebote, um das System kennenzulernen, und entdecken Sie, wie KI Ihren Arbeitsalltag erleichtern kann. Bei Fragen oder Anregungen freuen wir uns über Ihr Feedback!

