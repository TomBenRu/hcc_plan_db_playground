# WICHTIGER HINWEIS: String-Formatierung in Python

## PROBLEM IDENTIFIZIERT
Bei String-Formatierungs-Operationen wurde fälschlicherweise die Python-Escape-Sequenz `\n` als tatsächlicher Zeilenumbruch im Code interpretiert.

## KORREKTE INTERPRETATION
- `\n` ist die **Python-Code-Sequenz** für einen Zeilenumbruch
- `\n` wird **NICHT** als tatsächlicher Zeilenumbruch in den Quellcode eingefügt
- `\n` wird zur **Laufzeit** als Zeilenumbruch in der UI dargestellt

## BEISPIEL
```python
# RICHTIG - das ist Python-Code:
text = "Erste Zeile\nZweite Zeile"

# FALSCH - das wäre ein echter Zeilenumbruch im Quellcode:
text = "Erste Zeile
Zweite Zeile"
```

## AUSWIRKUNG
Diese Verwechslung führte in früheren Sessions zu:
- Fehlerhaften String-Ersetzungen mit Regex
- Kaputten f-String-Formatierungen  
- User musste mehrfach manuell korrigieren

## LÖSUNGSANSATZ
- Immer sorgfältig zwischen Python-Escape-Sequenzen und echten Zeilenumbrüchen unterscheiden
- Bei String-Operationen genau auf die Syntax achten
- Schrittweise und vorsichtige Code-Änderungen
