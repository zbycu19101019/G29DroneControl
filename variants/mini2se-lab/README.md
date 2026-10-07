# Wariant 3 — Mini 2 SE lab/symulator

Uruchomienie z katalogu głównego projektu:

```powershell
python .\variants\mini2se-lab\simulator.py
```

Następnie w drugim terminalu:

```powershell
python main.py --android
```

Symulator łączy się z tym samym strumieniem JSON przez port 8765. Gdy pakiety znikną na ponad 400 ms, model przechodzi do neutralnego stanu. Ten wariant nie otwiera USB RC-N1 i nie komunikuje się z DJI Fly.
