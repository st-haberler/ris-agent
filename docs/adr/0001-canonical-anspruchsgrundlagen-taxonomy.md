# Triage uses a canonical Anspruchsgrundlagen taxonomy, not the textbook's structure

Triage classifies questions by a fixed, textbook-independent scheme of Anspruchsgrundlage areas (Vertrag, Vorvertragliches Verhältnis, Dingliches Recht, Absolutes Recht, Schadenersatz, Bereicherungsrecht, Erbrecht, Familienrechtlicher Anspruch, plus the explicit outcome "Kein Privatrechtsanspruch erkennbar"). Each Textbook carries a hand-authored sidecar mapping (`data/textbooks/<book>.mapping.json`) from these areas to its own headline paths; empty mappings are allowed and reported as "not verifiable against this textbook".

## Considered Options

Using the textbook's own headline tree as the taxonomy was rejected: Zankl is organised by the Pandekten system (Allgemeiner Teil, Schuldrecht, Sachenrecht, Familienrecht, Erbrecht), which is one book's didactic order — the Anspruchsgrundlagen scheme is how a lawyer actually triages a case, and it stays stable when further textbooks with different structures are added. The mapping sidecar absorbs the mismatch per book and is validated against the textbook tree at load time, so edition changes fail loudly instead of silently misclassifying.
