from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from math import sin, cos, pi
import random
import time
import sys

# -----------------------------
# Camera, Player, World Config
# -----------------------------
WINDOW_W, WINDOW_H = 1200, 800

# Player (baby)
babyX, babyY, babyZ = 0.0, 0.0, 6.0
babySpeed = 0.12
legAngle = 0.0
legDir = 1
babyAlive = True
cheatMode = False

# Camera
camX, camY, camZ = 0.0, 4.5, 10.0
camLag = 0.1

# Targets (School -> Street -> Hospital -> Pharmacy)
targets = [
    (0.0, 0.0, 2.0),    # School front plaza
    (0.0, 0.0, -0.5),   # Crosswalk center
    (0.0, 0.0, -12.0),  # Hospital front
    (0.0, 0.0, -22.0)   # Pharmacy front
]
currentTarget = 0

# World Layout (Z axis forward/back, X axis left/right)
GROUND_Z_MIN, GROUND_Z_MAX = -30.0, 15.0
ROAD_Z_NEAR, ROAD_Z_FAR = -2.0, -10.0
ROAD_X_LEFT, ROAD_X_RIGHT = -10.0, 10.0
SIDEWALK_X_INNER = 7.5
CROSSWALK_Z = -6.0
STOP_LINE_Z = CROSSWALK_Z + 0.8  # where cars must stop

# Traffic Light State
# states: "GREEN_FOR_CARS" (default), "CHANGING_TO_RED", "RED_FOR_CARS"
trafficState = "GREEN_FOR_CARS"
lastButtonPressTime = None
buttonCooldown = 6.0         # seconds: how long red lasts for cars
changeDelay = 1.2            # seconds after pressing before red activates
buttonActive = False         # becomes True when E is pressed near pole

# Crosswalk Button Pole position
buttonPoleX, buttonPoleZ = -6.5, CROSSWALK_Z + 0.2
buttonPressDistance = 1.2

# Cars
# Each car: dict(x, y, z, dir, speed, alive)
# Lanes move along X; cars oscillate between ROAD_X_LEFT+1.2 and ROAD_X_RIGHT-1.2
cars = []
carBaseSpeed = 0.12
carBounds = (ROAD_X_LEFT+1.2, ROAD_X_RIGHT-1.2)
numCars = 5

# Traffic violation detection
# If a car's front crosses stop line while RED_FOR_CARS -> destroy
carLength = 1.8

# Elderly Pedestrian
elderlyExists = False
elderlyX, elderlyZ = -8.3, CROSSWALK_Z + 0.2  # on sidewalk near the pole
elderlyAppearances = 0
elderlySpawnInterval = (6.0, 14.0)  # random interval
nextElderlyTime = 0.0
elderlyStartDeadline = 60.0  # must appear >= 3 times within 60s
startTime = None

# Input
keys = {}

# Game State
gameOver = False
gameOverReason = ""

# -----------------------------
# Helpers
# -----------------------------
def reset_game():
    global babyX, babyY, babyZ, legAngle, legDir, babyAlive, cheatMode
    global camX, camY, camZ, currentTarget, trafficState, lastButtonPressTime
    global buttonActive, cars, elderlyExists, elderlyAppearances, nextElderlyTime
    global startTime, gameOver, gameOverReason

    babyX, babyY, babyZ = 0.0, 0.0, 6.0
    legAngle, legDir = 0.0, 1
    babyAlive = True
    cheatMode = False
    camX, camY, camZ = 0.0, 4.5, 10.0
    currentTarget = 0

    trafficState = "GREEN_FOR_CARS"
    lastButtonPressTime = None
    buttonActive = False

    # Spawn cars
    random.seed(42)  # stable for testing
    cars = []
    for i in range(numCars):
        laneZ = random.choice([-4.0, -5.0, -7.0, -8.5])
        x = random.uniform(carBounds[0], carBounds[1])
        dir = random.choice([-1.0, 1.0])
        sp = carBaseSpeed * random.uniform(0.8, 1.3)
        cars.append({"x": x, "y": 0.6, "z": laneZ, "dir": dir, "speed": sp, "alive": True})

    # Elderly rule
    elderlyExists = False
    elderlyAppearances = 0
    nextElderlyTime = 3.0  # spawn the first one early
    # Game time
    startTime = time.time()

    gameOver = False
    gameOverReason = ""

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def dist2(x1,z1,x2,z2):
    dx, dz = x1-x2, z1-z2
    return dx*dx + dz*dz

def draw_text_2d(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def within(a, b, eps=0.001):
    return abs(a-b) <= eps

# -----------------------------
# Rendering
# -----------------------------
def init_gl():
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL)
    glShadeModel(GL_SMOOTH)

    glClearColor(0.60, 0.78, 0.97, 1.0)  # soft sky
    glLightfv(GL_LIGHT0, GL_POSITION, [12, 30, 12, 1])
    glLightfv(GL_LIGHT0, GL_DIFFUSE,  [1, 1, 1, 1])

def reshape(w, h):
    global WINDOW_W, WINDOW_H
    WINDOW_W, WINDOW_H = max(1, w), max(1, h)
    glViewport(0, 0, WINDOW_W, WINDOW_H)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(60.0, WINDOW_W / float(WINDOW_H), 0.1, 200.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

def draw_ground():
    glColor3f(0.78, 0.89, 0.78)  # grass
    glBegin(GL_QUADS)
    glVertex3f(-50, 0, GROUND_Z_MIN)
    glVertex3f( 50, 0, GROUND_Z_MIN)
    glVertex3f( 50, 0, GROUND_Z_MAX)
    glVertex3f(-50, 0, GROUND_Z_MAX)
    glEnd()

def draw_road():
    # Road body
    glColor3f(0.18, 0.18, 0.18)
    glBegin(GL_QUADS)
    glVertex3f(ROAD_X_LEFT, 0, ROAD_Z_NEAR)
    glVertex3f(ROAD_X_RIGHT, 0, ROAD_Z_NEAR)
    glVertex3f(ROAD_X_RIGHT, 0, ROAD_Z_FAR)
    glVertex3f(ROAD_X_LEFT, 0, ROAD_Z_FAR)
    glEnd()

    # Sidewalks (professional wide)
    glColor3f(0.85, 0.85, 0.85)
    # Left sidewalk
    glBegin(GL_QUADS)
    glVertex3f(-12.0, 0.02, GROUND_Z_MIN)
    glVertex3f(ROAD_X_LEFT, 0.02, GROUND_Z_MIN)
    glVertex3f(ROAD_X_LEFT, 0.02, GROUND_Z_MAX)
    glVertex3f(-12.0, 0.02, GROUND_Z_MAX)
    glEnd()
    # Right sidewalk
    glBegin(GL_QUADS)
    glVertex3f(ROAD_X_RIGHT, 0.02, GROUND_Z_MIN)
    glVertex3f(12.0, 0.02, GROUND_Z_MIN)
    glVertex3f(12.0, 0.02, GROUND_Z_MAX)
    glVertex3f(ROAD_X_RIGHT, 0.02, GROUND_Z_MAX)
    glEnd()

    # Lane dividers
    glLineWidth(3.0)
    glColor3f(1, 1, 1)
    for z in [ROAD_Z_NEAR - 1.0, (ROAD_Z_NEAR+ROAD_Z_FAR)/2.0, ROAD_Z_FAR + 1.0]:
        glBegin(GL_LINES)
        glVertex3f(ROAD_X_LEFT+0.7, 0.03, z)
        glVertex3f(ROAD_X_RIGHT-0.7, 0.03, z)
        glEnd()

    # Zebra Crosswalk
    stripe_count = 12
    stripe_w = 0.35
    gap = 0.20
    total = stripe_count*(stripe_w+gap)
    startX = -4.5
    glColor3f(1, 1, 1)
    for i in range(stripe_count):
        x0 = startX + i*(stripe_w+gap)
        glBegin(GL_QUADS)
        glVertex3f(x0, 0.04, CROSSWALK_Z+0.7)
        glVertex3f(x0+stripe_w, 0.04, CROSSWALK_Z+0.7)
        glVertex3f(x0+stripe_w, 0.04, CROSSWALK_Z-0.7)
        glVertex3f(x0, 0.04, CROSSWALK_Z-0.7)
        glEnd()

    # Stop line (thick)
    glColor3f(1, 1, 0.6)
    glBegin(GL_QUADS)
    glVertex3f(ROAD_X_LEFT, 0.035, STOP_LINE_Z+0.03)
    glVertex3f(ROAD_X_RIGHT, 0.035, STOP_LINE_Z+0.03)
    glVertex3f(ROAD_X_RIGHT, 0.035, STOP_LINE_Z-0.03)
    glVertex3f(ROAD_X_LEFT, 0.035, STOP_LINE_Z-0.03)
    glEnd()

def draw_building(x, z, w, d, h, wallColor, windowColor=(0.75,0.9,1.0)):
    # Main block
    glColor3fv(wallColor)
    glPushMatrix()
    glTranslatef(x, h/2.0, z)
    glScalef(w, h, d)
    glutSolidCube(1)
    glPopMatrix()

    # Simple roof slab
    glColor3f(0.25, 0.25, 0.25)
    glPushMatrix()
    glTranslatef(x, h+0.05, z)
    glScalef(w*1.02, 0.1, d*1.02)
    glutSolidCube(1)
    glPopMatrix()

    # Windows grid (front face)
    glColor3fv(windowColor)
    cols, rows = 4, 3
    for ci in range(cols):
        for ri in range(rows):
            wx = x - (w/2.0) + (ci+0.5)*(w/cols)
            wy = 0.6 + ri*(h/(rows+1))
            wz = z + d/2.0 + 0.01
            glPushMatrix()
            glTranslatef(wx, wy, wz)
            glScalef(w/(cols*3.0), h/(rows*4.0), 0.02)
            glutSolidCube(1)
            glPopMatrix()

    # Door (front)
    glColor3f(0.40, 0.23, 0.12)
    glPushMatrix()
    glTranslatef(x, 0.6, z + d/2.0 + 0.02)
    glScalef(w*0.18, 1.2, 0.04)
    glutSolidCube(1)
    glPopMatrix()

def draw_button_pole():
    # Pole
    glColor3f(0.2, 0.2, 0.2)
    glPushMatrix()
    glTranslatef(buttonPoleX, 0.0, buttonPoleZ)
    glScalef(0.15, 2.0, 0.15)
    glutSolidCube(1)
    glPopMatrix()
    # Button box
    glColor3f(0.3, 0.3, 0.3)
    glPushMatrix()
    glTranslatef(buttonPoleX, 1.1, buttonPoleZ+0.15)
    glScalef(0.30, 0.25, 0.12)
    glutSolidCube(1)
    glPopMatrix()
    # Button light (green when ready, red when engaged)
    if trafficState == "GREEN_FOR_CARS":
        glColor3f(0.2, 0.8, 0.2)
    elif trafficState == "CHANGING_TO_RED":
        glColor3f(1.0, 0.8, 0.2)
    else:
        glColor3f(0.9, 0.1, 0.1)
    glPushMatrix()
    glTranslatef(buttonPoleX, 1.1, buttonPoleZ+0.22)
    glutSolidSphere(0.08, 16, 16)
    glPopMatrix()

def draw_traffic_light():
    # Traffic light post (on opposite sidewalk)
    postX, postZ = 6.5, CROSSWALK_Z + 0.2
    # Pole
    glColor3f(0.2, 0.2, 0.2)
    glPushMatrix()
    glTranslatef(postX, 0.0, postZ)
    glScalef(0.18, 3.2, 0.18)
    glutSolidCube(1)
    glPopMatrix()
    # Head
    glPushMatrix()
    glTranslatef(postX, 2.1, postZ+0.15)
    glScalef(0.6, 1.4, 0.3)
    glutSolidCube(1)
    glPopMatrix()

    # Lights
    def bulb(y, on, color_on, color_off=(0.1,0.1,0.1)):
        glColor3fv(color_on if on else color_off)
        glPushMatrix()
        glTranslatef(postX, y, postZ+0.31)
        glutSolidSphere(0.14, 18, 18)
        glPopMatrix()

    # Top Red, Middle Yellow, Bottom Green (for cars)
    isRed = (trafficState == "RED_FOR_CARS")
    isYellow = (trafficState == "CHANGING_TO_RED")
    isGreen = (trafficState == "GREEN_FOR_CARS")

    bulb(2.5, isRed,   (1.0, 0.0, 0.0))
    bulb(2.1, isYellow,(1.0, 0.85, 0.0))
    bulb(1.7, isGreen, (0.0, 1.0, 0.0))

    # Pedestrian "WALK" indicator facing crosswalk center
    walkX, walkZ = 0.0, CROSSWALK_Z + 0.2
    glColor3f(0.15, 0.15, 0.15)
    glPushMatrix()
    glTranslatef(walkX, 2.0, walkZ-1.2)
    glScalef(1.0, 0.5, 0.2)
    glutSolidCube(1)
    glPopMatrix()
    # Icon lamp
    walkAllowed = isRed  # pedestrians can walk when cars are red
    glColor3f(0.2, 1.0, 0.2) if walkAllowed else glColor3f(1.0, 0.2, 0.2)
    glPushMatrix()
    glTranslatef(walkX, 2.0, walkZ-1.0)
    glutSolidSphere(0.18, 16, 16)
    glPopMatrix()

def draw_baby():
    global legAngle
    # Torso
    glColor3f(1.0, 0.84, 0.70)
    glPushMatrix()
    glTranslatef(babyX, 0.9, babyZ)
    glScalef(0.45, 0.9, 0.30)
    glutSolidCube(1)
    glPopMatrix()
    # Head
    glPushMatrix()
    glTranslatef(babyX, 1.5, babyZ)
    glutSolidSphere(0.22, 20, 20)
    glPopMatrix()
    # Legs
    for i in [-1, 1]:
        glPushMatrix()
        glTranslatef(babyX+0.12*i, 0.45, babyZ)
        glRotatef(legAngle*i, 1, 0, 0)
        glScalef(0.10, 0.45, 0.10)
        glutSolidCube(1)
        glPopMatrix()

def draw_elderly():
    if not elderlyExists:
        return
    # Simple elderly woman figure with a cane
    glPushMatrix()
    glTranslatef(elderlyX, 0.0, elderlyZ)
    # Body
    glColor3f(0.85, 0.70, 0.85)
    glPushMatrix()
    glTranslatef(0.0, 0.9, 0.0)
    glScalef(0.5, 0.9, 0.35)
    glutSolidCube(1)
    glPopMatrix()
    # Head
    glColor3f(1.0, 0.86, 0.75)
    glPushMatrix()
    glTranslatef(0.0, 1.45, 0.0)
    glutSolidSphere(0.22, 16, 16)
    glPopMatrix()
    # Cane
    glColor3f(0.2, 0.2, 0.2)
    glPushMatrix()
    glTranslatef(0.18, 0.0, 0.05)
    glScalef(0.05, 1.0, 0.05)
    glutSolidCube(1)
    glPopMatrix()
    glPopMatrix()

def draw_car(car):
    if not car["alive"]:
        return
    glColor3f(0.9, 0.1, 0.1)
    glPushMatrix()
    glTranslatef(car["x"], car["y"], car["z"])
    glScalef(1.8, 0.6, 0.9)
    glutSolidCube(1)
    glPopMatrix()
    # Wheels
    glColor3f(0.05, 0.05, 0.05)
    for ox in [-0.7, 0.7]:
        for oz in [-0.3, 0.3]:
            glPushMatrix()
            glTranslatef(car["x"]+ox, car["y"]-0.35, car["z"]+oz)
            glutSolidTorus(0.07, 0.20, 10, 20)
            glPopMatrix()

def draw_targets():
    tx, _, tz = targets[currentTarget]
    glColor3f(1.0, 0.9, 0.2)
    glPushMatrix()
    glTranslatef(tx, 0.1, tz)
    glScalef(0.6, 0.1, 0.6)
    glutSolidCube(1)
    glPopMatrix()

def draw_scene():
    draw_ground()
    draw_road()

    # Buildings
    draw_building(0.0, 4.5, 10.0, 4.0, 5.0, (1.0, 0.98, 0.75))    # School
    draw_building(0.0, -14.5, 10.0, 4.0, 5.0, (0.75, 0.88, 1.0)) # Hospital
    draw_building(0.0, -24.5, 7.0, 3.0, 4.0, (1.0, 0.80, 0.80))  # Pharmacy

    draw_button_pole()
    draw_traffic_light()

    # Cars
    for car in cars:
        draw_car(car)

    # Characters
    draw_baby()
    draw_elderly()

    # Current target gizmo
    draw_targets()

# -----------------------------
# Logic & Update
# -----------------------------
def try_press_button():
    global buttonActive, lastButtonPressTime, trafficState
    if trafficState != "GREEN_FOR_CARS":
        return  # already changing or red
    # must be close enough to the button pole
    if dist2(babyX, babyZ, buttonPoleX, buttonPoleZ) <= buttonPressDistance**2:
        buttonActive = True
        lastButtonPressTime = time.time()
        trafficState = "CHANGING_TO_RED"

def update_traffic():
    global trafficState, lastButtonPressTime, buttonActive
    t = time.time()
    if trafficState == "CHANGING_TO_RED":
        # after small delay, become red
        if lastButtonPressTime and (t - lastButtonPressTime) >= changeDelay:
            trafficState = "RED_FOR_CARS"
            lastButtonPressTime = t  # reuse to time red duration
    elif trafficState == "RED_FOR_CARS":
        # stay red for buttonCooldown seconds
        if lastButtonPressTime and (t - lastButtonPressTime) >= buttonCooldown:
            trafficState = "GREEN_FOR_CARS"
            lastButtonPressTime = None
            buttonActive = False

def car_should_stop(car):
    # If traffic is red for cars, they should stop before stop line
    if trafficState != "RED_FOR_CARS":
        return False
    # If the car is approaching the stop line (depends on its direction)
    # Cars move along X, stop line is along Z; use proximity in Z to the crosswalk zone
    if abs(car["z"] - STOP_LINE_Z) <= 1.0:
        return True
    return False

def car_violation_and_destroy(car, next_x):
    # If red, and the car's "front" crosses the stop line strip in Z while close to crosswalk -> violation
    # Movement is in X only; we consider car entering the crosswalk band while red as violation
    if trafficState == "RED_FOR_CARS" and abs(car["z"] - STOP_LINE_Z) <= 0.6:
        # detect if car is intruding the crosswalk X range:
        # we consider crosswalk spans roughly [-5.0, 5.0] in X
        if (carBounds[0] <= next_x <= carBounds[1]) and (-5.0 <= next_x <= 5.0):
            car["alive"] = False

def update_cars():
    for car in cars:
        if not car["alive"]:
            continue
        stop = car_should_stop(car)
        speed = 0.0 if stop else car["speed"]
        next_x = car["x"] + car["dir"] * speed

        # Traffic violation (car continues while red and near crosswalk) -> destroy
        if trafficState == "RED_FOR_CARS" and not stop:
            car_violation_and_destroy(car, next_x)

        # Oscillate within bounds
        if next_x < carBounds[0]:
            next_x = carBounds[0]
            car["dir"] *= -1
        elif next_x > carBounds[1]:
            next_x = carBounds[1]
            car["dir"] *= -1

        car["x"] = next_x

def check_collision_baby_cars():
    if cheatMode or not babyAlive:
        return False
    # Simple AABB collision
    for car in cars:
        if not car["alive"]:
            continue
        # Baby bbox
        bx0, bx1 = babyX - 0.25, babyX + 0.25
        bz0, bz1 = babyZ - 0.25, babyZ + 0.25
        # Car bbox
        cx0, cx1 = car["x"] - 0.9, car["x"] + 0.9
        cz0, cz1 = car["z"] - 0.45, car["z"] + 0.45
        overlap = (bx0 <= cx1 and bx1 >= cx0 and bz0 <= cz1 and bz1 >= cz0)
        if overlap:
            return True
    return False

def maybe_spawn_elderly():
    global elderlyExists, elderlyAppearances, nextElderlyTime
    t = time.time()
    if t - startTime >= nextElderlyTime and not elderlyExists:
        elderlyExists = True
        elderlyAppearances += 1
        # schedule next spawn time from now
        nextElderlyTime += random.uniform(*elderlySpawnInterval)

def elderly_auto_despawn():
    # Keep her visible briefly, then despawn (simulate appearing)
    # We'll let her stay ~3 seconds after spawning
    global elderlyExists
    if not elderlyExists:
        return
    # simplistic: if baby is far for ~3 seconds, despawn
    # use distance + timer by piggybacking nextElderlyTime threshold
    # (Not perfect timing; good enough for the rule visualization.)
    # We’ll despawn when baby gets close to her or enough time passes.
    if dist2(babyX, babyZ, elderlyX, elderlyZ) < 2.5**2:
        elderlyExists = False

def enforce_elderly_rule():
    # If not at least 3 appearances within 60s, player dies (unless cheat)
    global gameOver, gameOverReason, babyAlive
    if cheatMode or gameOver:
        return
    elapsed = time.time() - startTime
    if elapsed >= elderlyStartDeadline and elderlyAppearances < 3:
        babyAlive = False
        gameOver = True
        gameOverReason = "Elderly woman did not appear at least 3 times within 60s."

def update_player():
    global babyX, babyZ, legAngle, legDir
    if not babyAlive:
        return
    s = babySpeed
    moving = False
    if keys.get(b"w"):
        babyZ -= s; moving = True
    if keys.get(b"s"):
        babyZ += s; moving = True
    if keys.get(b"a"):
        babyX -= s; moving = True
    if keys.get(b"d"):
        babyX += s; moving = True

    # Clamp within a broad play area
    babyX = clamp(babyX, -11.5, 11.5)
    babyZ = clamp(babyZ, GROUND_Z_MIN+1.0, GROUND_Z_MAX-1.0)

    # Leg animation
    if moving:
        legAngle += legDir * 5.0
        if legAngle > 30 or legAngle < -30:
            legDir *= -1
    else:
        # ease back towards 0
        legAngle *= 0.85
        if abs(legAngle) < 0.5:
            legAngle = 0.0

def update_targets():
    global currentTarget
    if currentTarget >= len(targets)-1:
        return
    tx, _, tz = targets[currentTarget]
    if abs(babyX - tx) < 0.6 and abs(babyZ - tz) < 0.6:
        currentTarget += 1

def update_camera():
    global camX, camY, camZ
    # smooth follow
    cx = babyX
    cz = babyZ + 8.0
    cy = 4.5
    camX += (cx - camX) * camLag
    camY += (cy - camY) * camLag
    camZ += (cz - camZ) * camLag

def update(value):
    global gameOver, gameOverReason, babyAlive

    if not gameOver:
        update_player()
        update_traffic()
        update_cars()
        maybe_spawn_elderly()
        elderly_auto_despawn()
        enforce_elderly_rule()

        if check_collision_baby_cars():
            if not cheatMode:
                babyAlive = False
                gameOver = True
                gameOverReason = "Hit by a car!"
        update_targets()
        update_camera()

    glutPostRedisplay()
    glutTimerFunc(16, update, 0)  # ~60 FPS

# -----------------------------
# Input
# -----------------------------
def keyboard(key, x, y):
    global cheatMode
    if key == b'\x1b':  # ESC
        sys.exit(0)
    keys[key.lower()] = True

    if key.lower() == b'c':
        cheatMode = not cheatMode
    elif key.lower() == b'e':
        try_press_button()
    elif key.lower() == b'r':
        if gameOver:
            reset_game()
    elif key.lower() == b'n':
        # debug: force-spawn elderly (counts as an appearance)
        global elderlyExists, elderlyAppearances
        if not elderlyExists:
            elderlyExists = True
            elderlyAppearances += 1

def keyboardUp(key, x, y):
    keys[key.lower()] = False

# -----------------------------
# Display & HUD
# -----------------------------
def display():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()

    # Camera
    gluLookAt(camX, camY, camZ, babyX, 1.0, babyZ, 0, 1, 0)

    # Scene
    draw_scene()

    # HUD
    glDisable(GL_LIGHTING)
    hud_y = WINDOW_H - 30
    draw_text_2d(20, hud_y, "NDD Spatial Navigation Trainer")
    hud_y -= 24
    draw_text_2d(20, hud_y, f"Cheat Mode: {'ON' if cheatMode else 'OFF'}    Elderly Appearances: {elderlyAppearances}/3")
    hud_y -= 24
    # Traffic status
    tstate = {
        "GREEN_FOR_CARS": "Cars: GREEN  | Pedestrians: WAIT",
        "CHANGING_TO_RED": "Cars: YELLOW | Pedestrians: WAIT",
        "RED_FOR_CARS": "Cars: RED    | Pedestrians: WALK"
    }[trafficState]
    draw_text_2d(20, hud_y, f"Traffic: {tstate}")
    hud_y -= 24
    draw_text_2d(20, hud_y, "Press E near the button pole to request crossing.")

    # Timer for elderly rule
    elapsed = max(0, int(time.time() - startTime)) if startTime else 0
    remaining = max(0, int(elderlyStartDeadline - elapsed))
    hud_y -= 24
    draw_text_2d(20, hud_y, f"Elderly rule check in: {remaining:02d}s")

    # Game Over
    if gameOver:
        draw_text_2d(WINDOW_W//2 - 120, WINDOW_H//2 + 20, "*** GAME OVER ***", GLUT_BITMAP_HELVETICA_18)
        draw_text_2d(WINDOW_W//2 - 260, WINDOW_H//2 - 10, f"Reason: {gameOverReason}", GLUT_BITMAP_HELVETICA_18)
        draw_text_2d(WINDOW_W//2 - 220, WINDOW_H//2 - 40, "Press R to Restart", GLUT_BITMAP_HELVETICA_18)

    glEnable(GL_LIGHTING)
    glutSwapBuffers()

# -----------------------------
# Main
# -----------------------------
def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WINDOW_W, WINDOW_H)
    glutCreateWindow(b"NDD Spatial Navigation Trainer - Professional Build")

    init_gl()
    glutDisplayFunc(display)
    glutReshapeFunc(reshape)
    glutKeyboardFunc(keyboard)
    glutKeyboardUpFunc(keyboardUp)
    reset_game()
    glutTimerFunc(16, update, 0)
    glutMainLoop()

if __name__ == "__main__":
    main()
