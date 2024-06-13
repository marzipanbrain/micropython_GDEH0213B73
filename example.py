
from GDEH0213B73 import GDHE0213B73

# Constructor initializes the display
epaper = GDHE0213B73(orientation=GDHE0213B73.LANDSCAPE)
# LANDSCAPE:  X: 0->249, Y: 0->121, width: 250, height: 122
# PORTRAIT:   X: 0->121, Y: 0->249, width: 122, height: 250
epaper.fill(1)
epaper.text("Hello World!", 0, 0, 0)
epaper.textWrap("The quick brown fox jumps over the lazy dog.", 90, 32, 0, 160, 32, None)
# Filled circle
epaper.ellipse(120, 85, 20, 20, 0, True)
# line drawing of 3d cube
epaper.linePath(180, 85, (-10, -5, 0, -10, 10, -5, 10, 7.5, 0, 12.5, -10, 7.5, -10, -5, 0, 0, 0, 12.5, 0, 0, 10, -5), 0, 2.0)
# Nested rectangles
for step in range(0, 80, 10):
    epaper.rect(step, step+16, 80-step*2, 80-step*2, 0, False)
epaper.show()
epaper.deepSleep()