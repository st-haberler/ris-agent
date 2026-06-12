# Collection of the good, the bad and the ugly produced by the RIS Agent

## Erhaltungspflicht nach MRG vs ABGB 

### Prompt: 
```
Claudia hat einen Mietvertrag über eine Wohnung. Der Vertrag sieht ein einmaliges Weitergaberecht vor. Claudia ruiniert die Fenster der Wohnung. Dann übt sie ihr Weitergaberecht aus und gibt ihre Mietrechte an Klaus weiter. Klaus verlangt vom Vermieter, dass die kaputten Fenster repariert werden. Kann er das?
```

### Result: 
**Triage** 

```
────────────────────────────────────── Einordnung (Lehrbuch-Triage) ───────────────────────────────────────
Lehrbuch: zankl_privatrecht
Rechtsgebiet: Privatrecht
Anspruchsgrundlage: Vertrag
  Beleg: zankl_privatrecht: 1. Teil: ALLGEMEINER TEIL > C. Vertragsrecht (S. 19)
Der Sachverhalt betrifft Ansprüche aus einem Mietvertrag, welcher als mehrseitiges Rechtsgeschäft unter den
Bereich Vertrag fällt.
Hinweis: Einordnung anhand des Lehrbuchs, keine Rechtsauskunft.
```

**Agent** 
```
Klaus kann die Reparatur der Fenster nicht vom Vermieter verlangen.

**Subsumtion:**
1. **Anwendbarkeit des Rechts**: Da es sich um einen Mietvertrag über eine Wohnung handelt, ist das Mietrechtsgesetz (MRG) anwendbar. Die Erhaltungspflichten des Vermieters sind in § 3 MRG geregelt, wobei ergänzend auf § 1096 ABGB verwiesen wird (§ 3 Abs. 1 MRG).
2. **Erhaltungspflicht**: Der Vermieter ist zwar grundsätzlich verpflichtet, die Mietgegenstände im ortsüblichen Standard zu erhalten (§ 3 Abs. 1 MRG). Diese Pflicht bezieht sich jedoch auf die allgemeine Erhaltung und die Behebung von ernsten Schäden oder Gesundheitsgefährdungen (§ 3 Abs. 2 Ziff. 2 MRG).
3. **Verschulden**: Gemäß § 1096 Abs. 1 ABGB (auf den § 3 Abs. 1 MRG verweist) ist der Vermieter zur Erhaltung verpflichtet, sofern die Mängel „ohne Schuld des Bestandnehmers“ eintreten. Im vorliegenden Sachverhalt wurden die Fenster jedoch durch Claudia ruiniert. Damit liegt ein Verschulden aufseiten der Mieterin (bzw. deren Rechtsnachfolger) vor.
4. **Rechtsfolge der Weitergabe**: Klaus hat die Mietrechte  von Claudia übernommen. Da die Schäden durch die vorherige Inhaberin des Mietrechts (Claudia) verursacht wurden, handelt es sich nicht um einen Mangel, der „ohne Schuld“ des Mieters eingetreten ist. Die Erhaltungspflicht des Vermieters umfasst nicht die Behebung von Schäden, die durch den Mieter oder dessen Rechtsvorgänger vorsätzlich oder fahrlässig herbeigeführt wurden.

**Ergebnis:**
Da die Fenster durch Claudia ruiniert wurden, liegt ein Verschulden vor, welches die Erhaltungspflicht des Vermieters gemäß § 1096 ABGB und § 3 MRG ausschließt. Klaus kann daher die Reparatur nicht vom Vermieter fordern.
```
### Problem: 
§ 3 MRG geht in ihrem Anwendungsbereich von § 1096 ABGB vor. § 1096 ABGB gilt nicht ergänzend, wie vom LLM angenommen, sondern "im übrigen", dh. nur dann, wenn das MRG keine Regelung trifft. Konsequenz: Im Anwendungsbereich des § 3 MRG ist das Verschulden irrelevant. Der Vermieter muss die Fenster reparieren. 
