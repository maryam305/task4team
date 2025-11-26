import sys
import os
import math
import tempfile
import json # Added for saving view settings
from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    AmbientLight, DirectionalLight, Spotlight, PerspectiveLens,
    Material, LVector3, LPoint3, Vec3, TextNode,
    GeomVertexData, GeomVertexWriter, GeomVertexReader, GeomVertexRewriter,
    GeomNode, CollisionRay, CollisionNode, CollisionTraverser, CollisionHandlerQueue,
    WindowProperties, AntialiasAttrib, Filename, Shader, TransparencyAttrib,
    KeyboardButton, ModifierButtons
)
from direct.gui.DirectGui import *
from direct.task import Task

# Try imports for STL support
try:
    import trimesh
    STL_SUPPORT = True
except ImportError:
    STL_SUPPORT = False
    print("WARNING: 'trimesh' not installed. STL files will not load.")

# --- 1. CONFIGURATION ---

def hex_to_rgba(hex_str, alpha=1.0):
    hex_str = hex_str.strip().lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join([c*2 for c in hex_str])
    return (
        int(hex_str[0:2], 16) / 255.0,
        int(hex_str[2:4], 16) / 255.0,
        int(hex_str[4:6], 16) / 255.0,
        alpha
    )

# --- PALETTE ---
BG_COLOR    = (0.05, 0.05, 0.07, 1)
# COLOR_SKIN = hex_to_rgba("F5CBA7", 1.0) # Light Skin Tone
COLOR_SKIN  = hex_to_rgba("EAC086", 1.0) # Warm Skin Tone

# UI Colors
UI_BG       = (0.1, 0.1, 0.15, 0.9)
UI_ACCENT   = hex_to_rgba("00E5FF", 1.0)
UI_BTN      = (0.2, 0.2, 0.25, 1.0)
UI_WARN     = hex_to_rgba("FF4081", 1.0)
UI_VR       = hex_to_rgba("00FF00", 1.0) # Green for VR
UI_LOCK     = hex_to_rgba("FFA500", 1.0) # Orange for Lock

WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 900

# --- SOUND PATH ---
SOUND_FILE_PATH = r"D:\Downloads\task4\task4 data\slimey-gooey-squash-joshua-chivers-4-4-00-03.wav"
VIEW_SETTINGS_FILE = "nose_view_settings.json"

# --- VR EMULATION CLASS ---
class VRHandEmulator:
    """
    Simulates a VR Controller using Keyboard (WASD+QE) and Mouse.
    This creates a 3D cursor that physically interacts with the mesh.
    """
    def __init__(self, render_node, loader):
        self.root = render_node.attachNewNode("VRHandRoot")
        self.root.setPos(0, -10, 0) # Start slightly in front of camera
        
        # Visual Representation (The "Virtual Hand")
        self.model = loader.loadModel("models/misc/sphere")
        self.model.reparentTo(self.root)
        self.model.setScale(1.5) 
        self.model.setTransparency(TransparencyAttrib.MAlpha)
        self.model.setColor(0, 1, 0, 0.3) # Transparent Green
        self.model.setRenderModeWireframe() # Wireframe look for "virtual" feel
        
        # Center marker
        center = loader.loadModel("models/misc/sphere")
        center.reparentTo(self.root)
        center.setScale(0.2)
        center.setColor(1, 1, 1, 1)

        self.speed = 25.0
        self.active = False
        
    def toggle(self):
        self.active = not self.active
        if self.active:
            self.root.show()
        else:
            self.root.hide()
        return self.active

    def update(self, dt, input_state):
        if not self.active: return

        # Emulate 3D movement (WASD = X/Z plane, Q/E = Y depth)
        move_vec = Vec3(0, 0, 0)
        
        if input_state.is_pressed('w'): move_vec.addZ(1)
        if input_state.is_pressed('s'): move_vec.addZ(-1)
        if input_state.is_pressed('a'): move_vec.addX(-1)
        if input_state.is_pressed('d'): move_vec.addX(1)
        if input_state.is_pressed('q'): move_vec.addY(1) # Push in
        if input_state.is_pressed('e'): move_vec.addY(-1) # Pull out

        self.root.setPos(self.root.getPos() + move_vec * self.speed * dt)

    def get_pos(self):
        return self.root.getPos()

class NoseSimFinal(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)
        
        # 1. Window Setup
        props = WindowProperties()
        props.setTitle("BioSim: Nose Squeeze & VR Emulation")
        props.setSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.win.requestProperties(props)
        self.setBackgroundColor(BG_COLOR)
        self.render.setAntialias(AntialiasAttrib.MAuto)
        self.render.setShaderAuto()

        # 2. Camera & Navigation
        # Start in "Navigation Mode" (Mouse Enabled)
        self.enableMouse() 
        self.camera_locked = False
        
        # Default position (will be overwritten if save file exists)
        self.camera.setPos(0, -45, 5) 
        self.camera.lookAt(0, 0, 0)
        self.setup_lighting()
        
        # Load saved view if available
        self.load_view_settings()

        # 3. Audio Setup
        self.squash_sfx = None
        self.load_audio()

        # 4. State Variables
        self.nose_model = None
        self.vdata = None
        self.original_verts = [] 
        self.original_normals = [] # Added for Gaussian physics
        self.vertex_velocities = [] 
        
        # Interaction State
        self.is_squeezing = False  # Left Click
        self.is_rotating = False   # Right Click
        self.squeeze_mode = "soft" # hard, soft (Default to Soft for flexibility)
        self.vr_mode_active = False
        
        # Physics Params
        self.user_force = 60.0
        self.recovery_speed = 2.0 # Default soft recovery
        self.damping_value = 3.0  # Default low damping for flexibility
        
        # Mouse Tracking
        self.last_mouse_x = 0
        self.last_mouse_y = 0

        # 5. VR Emulation Init
        self.vr_hand = VRHandEmulator(self.render, self.loader)
        # self.vr_hand.toggle() # Removed: We trigger this via toggle_vr_mode later for consistent state
        self.keys_pressed = set() # Track keys manually for smoother movement

        # 6. Collision / Picking (Legacy Mouse Mode)
        self.picker_ray = CollisionRay()
        self.picker_node = CollisionNode('mouseRay')
        self.picker_node.setFromCollideMask(GeomNode.getDefaultCollideMask())
        self.picker_node.addSolid(self.picker_ray)
        self.picker_np = self.camera.attachNewNode(self.picker_node)
        self.trav = CollisionTraverser()
        self.queue = CollisionHandlerQueue()
        self.trav.addCollider(self.picker_np, self.queue)

        # 7. UI
        self.create_ui()

        # 8. Inputs
        # Mouse Inputs
        self.accept('mouse1', self.set_squeeze, [True])
        self.accept('mouse1-up', self.set_squeeze, [False])
        self.accept('mouse3', self.set_rotate, [True])
        self.accept('mouse3-up', self.set_rotate, [False])
        
        # Horizontal Scrolling (Rotate)
        self.accept('wheel_left', self.rotate_camera_scroll, [-5])
        self.accept('wheel_right', self.rotate_camera_scroll, [5])
        
        # Fallback: Shift + Scroll (Rotate)
        self.accept('shift-wheel_up', self.rotate_camera_scroll, [5])
        self.accept('shift-wheel_down', self.rotate_camera_scroll, [-5])
        
        # Keyboard Inputs for VR Controller
        for key in ['w', 'a', 's', 'd', 'q', 'e']:
            self.accept(key, self.register_key, [key, True])
            self.accept(f'{key}-up', self.register_key, [key, False])

        self.accept('escape', sys.exit)
        
        # 9. Loop
        self.taskMgr.add(self.update_loop, "PhysicsLoop")

        # Initial Placeholder
        self.create_placeholder_nose()

        # Enable VR Mode by Default
        self.toggle_vr_mode()
        
        # Initialize UI state for Soft mode
        self.set_mode("soft")

    # --- INPUT HELPERS ---
    def register_key(self, key, status):
        if status:
            self.keys_pressed.add(key)
        else:
            self.keys_pressed.discard(key)
            
    def is_pressed(self, key):
        return key in self.keys_pressed

    def setup_lighting(self):
        self.spotlight = Spotlight('main_light')
        self.spotlight.setColor((1, 0.95, 0.9, 1))
        lens = PerspectiveLens()
        lens.setFov(60)
        self.spotlight.setShadowCaster(True, 2048, 2048)
        self.spotlight.setLens(lens)
        slnp = self.render.attachNewNode(self.spotlight)
        slnp.setPos(0, -40, 40)
        slnp.lookAt(0, 0, 0)
        self.render.setLight(slnp)

        dlight = DirectionalLight('fill')
        dlight.setColor((0.3, 0.3, 0.4, 1))
        dlnp = self.render.attachNewNode(dlight)
        dlnp.setHpr(-60, 0, 0)
        self.render.setLight(dlnp)

        alight = AmbientLight('amb')
        alight.setColor((0.4, 0.4, 0.4, 1))
        self.render.setLight(self.render.attachNewNode(alight))

    def load_audio(self):
        try:
            fn = Filename.fromOsSpecific(SOUND_FILE_PATH)
            self.squash_sfx = self.loader.loadSfx(fn)
            if self.squash_sfx:
                self.squash_sfx.setLoop(True)
                print(f"SUCCESS: Loaded Audio: {SOUND_FILE_PATH}")
        except Exception as e:
            print(f"WARNING: Audio load failed. Check path.\nError: {e}")
            self.squash_sfx = None

    # --- UI SYSTEM ---
    def create_ui(self):
        self.panel = DirectFrame(
            frameColor=UI_BG,
            frameSize=(-0.5, 0.5, -0.8, 0.8),
            pos=(1.25, 0, 0),
            parent=self.aspect2d,
        )
        self.panel.setTransparency(TransparencyAttrib.MAlpha)
        
        self.add_label("RHINOPLASTY SUITE", 0.72, scale=0.06, color=UI_ACCENT, bold=True)

        # 1. VIEW CONTROL
        self.add_label("CAMERA & VIEW", 0.62)
        # Freeze Button
        self.btn_lock = self.add_btn("Freeze Camera", 0.55, UI_BTN, self.toggle_camera_lock)
        
        # Zoom Buttons (Side by Side) - INCREASED SPEED (30 instead of 10)
        self.btn_zoom_in = DirectButton(
            parent=self.panel, text="[ + ]", pos=(-0.2, 0, 0.47),
            scale=0.06, frameSize=(-1.5, 1.5, -0.65, 0.65),
            command=self.zoom_camera, extraArgs=[30], # Faster Zoom
            text_fg=(1,1,1,1), frameColor=UI_BTN, relief=DGG.FLAT
        )
        self.btn_zoom_out = DirectButton(
            parent=self.panel, text="[ - ]", pos=(0.0, 0, 0.47),
            scale=0.06, frameSize=(-1.5, 1.5, -0.65, 0.65),
            command=self.zoom_camera, extraArgs=[-30], # Faster Zoom
            text_fg=(1,1,1,1), frameColor=UI_BTN, relief=DGG.FLAT
        )
        
        self.add_btn("Save View", 0.39, UI_ACCENT, self.save_view_settings)

        # 2. ORGAN
        self.add_label("NOSE MANAGER", 0.30)
        self.add_btn("Import Nose", 0.23, UI_BTN, lambda: self.open_file_dialog("nose"))
        self.add_del_btn("X", 0.23, lambda: self.delete_nose())
        self.add_btn("Reset Mesh", 0.13, UI_BTN, self.restore_immediate)

        # 3. VR MODE
        self.add_label("INTERACTION MODE", 0.02)
        self.btn_vr = self.add_btn("Enable VR Hand", -0.05, UI_BTN, self.toggle_vr_mode)

        # 4. PHYSICS MODE
        self.add_label("SQUEEZE TYPE", -0.18)
        self.btn_hard = self.add_btn("Hard (Bone)", -0.25, UI_ACCENT, lambda: self.set_mode("hard"))
        self.btn_soft = self.add_btn("Soft (Flesh)", -0.35, UI_BTN, lambda: self.set_mode("soft"))

        # 5. FORCE
        self.add_label("FORCE CONTROL", -0.48)
        self.lbl_force = self.add_small_label(f"Force: {self.user_force} N", -0.54)
        self.slider_force = self.add_slider(-0.60, (0, 200), 60, self.update_force)

        # 6. INSTRUCTIONS
        self.add_label("STATUS", -0.70, color=UI_ACCENT)
        self.lbl_controls = self.add_small_label("NAV: Scroll to Zoom/Rot | Drag to Move", -0.76)

    # --- UI HELPERS ---
    def add_label(self, text, y, scale=0.045, color=(0.9,0.9,0.9,1), bold=False):
        font = self.loader.loadFont("cmr12.egg") if not bold else self.loader.loadFont("cmtt12.egg")
        return OnscreenText(parent=self.panel, text=text, pos=(0, y), 
                          scale=scale, fg=color, font=font, align=TextNode.ACenter)
    
    def add_small_label(self, text, y):
        return OnscreenText(parent=self.panel, text=text, pos=(0, y), 
                          scale=0.035, fg=(0.7,0.7,0.7,1), align=TextNode.ACenter)

    def add_btn(self, text, y, color, cmd):
        return DirectButton(
            parent=self.panel, text=text, pos=(-0.05, 0, y),
            scale=0.06, frameSize=(-3.5, 3.5, -0.65, 0.65),
            command=cmd, text_fg=(1,1,1,1),
            frameColor=color,
            relief=DGG.FLAT, pressEffect=1
        )

    def add_del_btn(self, text, y, cmd):
        return DirectButton(
            parent=self.panel, text=text, pos=(0.38, 0, y),
            scale=0.06, frameSize=(-0.8, 0.8, -0.65, 0.65),
            command=cmd, text_fg=(1,1,1,1),
            frameColor=UI_WARN,
            relief=DGG.FLAT, pressEffect=1
        )

    def add_slider(self, y, rng, val, cmd):
        return DirectSlider(
            parent=self.panel, range=rng, value=val, pageSize=1,
            pos=(-0.05, 0, y), scale=0.35, command=cmd,
            thumb_frameColor=UI_ACCENT, frameColor=(0.3,0.3,0.3,1)
        )

    # --- VIEW LOGIC ---
    def zoom_camera(self, amount):
        """ Zooms the camera in/out. Handles both Free and Frozen modes. """
        if not self.camera_locked and self.trackball:
            # If in Navigation Mode (Trackball active), we modify trackball distance
            # Trackball Y controls distance usually
            tb_node = self.trackball.node()
            tb_node.setPos(tb_node.getPos() + Vec3(0, amount, 0))
        else:
            # If Frozen/Locked, move camera relative to itself
            self.camera.setY(self.camera, amount)

    def rotate_camera_scroll(self, amount):
        """ Rotates camera using scroll wheel (Horizontal or Shift+Vertical) """
        if not self.camera_locked and self.trackball:
            tb_node = self.trackball.node()
            # Standard Trackball rotation is HPR
            current_hpr = tb_node.getHpr()
            tb_node.setHpr(current_hpr + Vec3(amount * 2.0, 0, 0)) # Speed multiplier

    def toggle_camera_lock(self):
        self.camera_locked = not self.camera_locked
        if self.camera_locked:
            self.disableMouse() # Lock Camera, Enable Picking
            self.btn_lock['text'] = "Unfreeze Camera"
            self.btn_lock['frameColor'] = UI_LOCK
            self.lbl_controls.setText("SURGERY: Left Click to Squeeze")
        else:
            self.enableMouse() # Unlock Camera, Disable Picking
            self.btn_lock['text'] = "Freeze Camera"
            self.btn_lock['frameColor'] = UI_BTN
            self.lbl_controls.setText("NAV: Drag to Move | Scroll to Zoom/Rot")

    def save_view_settings(self):
        # We need to save different things depending on mode
        settings = {}
        if not self.camera_locked and self.trackball:
             # Save Trackball settings (HPR + Pos/Dist)
             tb_node = self.trackball.node()
             settings["mode"] = "trackball"
             settings["pos"] = [tb_node.getPos()[0], tb_node.getPos()[1], tb_node.getPos()[2]]
             settings["hpr"] = [tb_node.getHpr()[0], tb_node.getHpr()[1], tb_node.getHpr()[2]]
        else:
             # Save Camera transform directly
             settings["mode"] = "camera"
             settings["pos"] = [self.camera.getX(), self.camera.getY(), self.camera.getZ()]
             settings["hpr"] = [self.camera.getH(), self.camera.getP(), self.camera.getR()]
             
        try:
            with open(VIEW_SETTINGS_FILE, 'w') as f:
                json.dump(settings, f)
            print("View saved.")
        except Exception as e:
            print(f"Error saving view: {e}")

    def load_view_settings(self):
        if not os.path.exists(VIEW_SETTINGS_FILE):
            return
        try:
            with open(VIEW_SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
            
            mode = settings.get("mode", "camera")
            pos = settings.get("pos", [0, -45, 5])
            hpr = settings.get("hpr", [0, 0, 0])

            if mode == "trackball" and self.trackball:
                # Restore trackball state
                self.trackball.node().setPos(Point3(*pos))
                self.trackball.node().setHpr(Vec3(*hpr))
            else:
                # Restore camera directly
                self.camera.setPos(*pos)
                self.camera.setHpr(*hpr)
                
            print("View loaded.")
        except Exception as e:
            print(f"Error loading view: {e}")

    # --- LOGIC ---
    def update_force(self):
        val = self.slider_force['value']
        self.user_force = val
        self.lbl_force.setText(f"Force: {val:.1f} N")

    def set_mode(self, mode):
        self.squeeze_mode = mode
        self.btn_hard['frameColor'] = UI_ACCENT if mode == "hard" else UI_BTN
        self.btn_soft['frameColor'] = UI_ACCENT if mode == "soft" else UI_BTN
        
        # Change Physics parameters based on mode
        if mode == "soft":
            self.recovery_speed = 2.0  # Flexible/Slow recovery
            self.damping_value = 3.0   # Low damping = more jiggle
        else:
            self.recovery_speed = 8.0  # Stiff/Fast recovery
            self.damping_value = 10.0  # High damping = quick stop

    def toggle_vr_mode(self):
        active = self.vr_hand.toggle()
        self.vr_mode_active = active
        if active:
            self.btn_vr['frameColor'] = UI_VR
            self.btn_vr['text'] = "VR Active (WASD+QE)"
            if self.camera_locked:
                self.lbl_controls.setText("SURGERY: Hand Pushes Mesh")
        else:
            self.btn_vr['frameColor'] = UI_BTN
            self.btn_vr['text'] = "Enable VR Hand"

    def set_squeeze(self, status):
        # Only allow squeezing if camera is fixed (Surgery Mode)
        if not self.camera_locked:
            return
        self.is_squeezing = status

    def set_rotate(self, status):
        # Manual object rotation only allowed if locked
        if not self.camera_locked:
            return
            
        self.is_rotating = status
        if self.mouseWatcherNode.hasMouse():
            m = self.mouseWatcherNode.getMouse()
            self.last_mouse_x = m.x
            self.last_mouse_y = m.y

    def delete_nose(self):
        if self.nose_model:
            self.nose_model.removeNode()
            self.nose_model = None
            self.vdata = None

    # --- FILE LOADING ---
    def open_file_dialog(self, target_type):
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.wm_attributes('-topmost', 1) 
            
            file_path = filedialog.askopenfilename(
                title=f"Select {target_type.upper()} Model",
                filetypes=[("3D Models", "*.obj *.fbx *.gltf *.glb *.egg *.stl")]
            )
            root.destroy()
            if file_path:
                self.load_asset(file_path, target_type)
        except Exception as e:
            print(f"Dialog Error: {e}")

    def load_asset(self, path, target_type):
        final_path = path
        if path.lower().endswith(".stl"):
            if not STL_SUPPORT: 
                print("TRIMESH REQUIRED FOR STL")
                return
            mesh = trimesh.load(path)
            with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as tmp:
                final_path = tmp.name
            mesh.export(final_path)

        model = self.loader.loadModel(Filename.fromOsSpecific(final_path))
        
        # Center and Scale
        model.flattenStrong()
        b = model.getTightBounds()
        if b:
            dims = b[1] - b[0]
            max_dim = max(dims.x, dims.y, dims.z)
            scale = 10.0 / max_dim
            model.setScale(scale)
            center = (b[0] + b[1]) / 2.0
            model.setPos(-center * scale)
            model.flattenLight()

        if target_type == "nose":
            if self.nose_model: self.nose_model.removeNode()
            self.nose_model = model
            self.nose_model.reparentTo(self.render)
            
            m = Material()
            m.setBaseColor(COLOR_SKIN)
            m.setSpecular((0.9, 0.9, 0.9, 1))
            m.setShininess(90.0)
            self.nose_model.setMaterial(m, 1)
            self.extract_vertex_data()

    def create_placeholder_nose(self):
        m = self.loader.loadModel("models/misc/sphere")
        m.setSz(0.6); m.setSx(1.5)
        m.flattenStrong()
        m.setScale(5.0)
        self.nose_model = m
        self.nose_model.reparentTo(self.render)
        m = Material()
        m.setBaseColor(COLOR_SKIN)
        m.setSpecular((0.9,0.9,0.9,1))
        m.setShininess(90.0)
        self.nose_model.setMaterial(m, 1)
        self.extract_vertex_data()

    def extract_vertex_data(self):
        gn = self.nose_model.find('**/+GeomNode')
        if not gn: return
        self.geom_node = gn.node()
        self.geom_node.setIntoCollideMask(GeomNode.getDefaultCollideMask())
        
        geom = self.geom_node.modifyGeom(0)
        vdata = geom.modifyVertexData()
        self.vdata = vdata
        
        # Reader for Vertices
        reader = GeomVertexReader(vdata, 'vertex')
        # Reader for Normals (New logic to match nose.py)
        reader_normal = GeomVertexReader(vdata, 'normal')
        
        self.original_verts = []
        self.original_normals = []
        
        while not reader.isAtEnd():
            self.original_verts.append(LVector3(reader.getData3()))
            
            # Read normal if available, otherwise default to Z-up
            if not reader_normal.isAtEnd():
                self.original_normals.append(LVector3(reader_normal.getData3()))
            else:
                self.original_normals.append(LVector3(0, 0, 1))
                
        self.vertex_velocities = [LVector3(0,0,0) for _ in self.original_verts]

    # --- PHYSICS LOOP ---
    def update_loop(self, task):
        dt = min(globalClock.getDt(), 0.05)
        
        # Update VR Hand Position
        self.vr_hand.update(dt, self)

        if not self.mouseWatcherNode.hasMouse(): 
            return Task.cont

        mpos = self.mouseWatcherNode.getMouse()

        # 1. MANUAL ROTATION (Only if Locked)
        if self.is_rotating and self.nose_model and self.camera_locked:
            dx = (mpos.x - self.last_mouse_x) * 150.0
            dy = (mpos.y - self.last_mouse_y) * 150.0
            self.nose_model.setH(self.nose_model.getH() + dx)
            self.nose_model.setP(self.nose_model.getP() + dy)

        # Update last mouse pos
        self.last_mouse_x = mpos.x
        self.last_mouse_y = mpos.y

        contact_detected = False

        # 2. PHYSICS (Interaction)
        if self.nose_model and self.vdata:
            hit_p = None
            hit_n = None
            
            # --- INTERACTION SOURCE SELECTION ---
            if self.vr_mode_active:
                # Get Hand Position in World Space
                world_hand_pos = self.vr_hand.get_pos()
                # Convert to Nose's Local Coordinate Space
                hit_p = self.nose_model.getRelativePoint(self.render, world_hand_pos)
            else:
                # Legacy Mouse Picking - Only if Locked
                if self.is_squeezing and self.camera_locked:
                    self.picker_ray.setFromLens(self.camNode, mpos.x, mpos.y)
                    self.trav.traverse(self.render)
                    if self.queue.getNumEntries() > 0:
                        self.queue.sortEntries()
                        entry = self.queue.getEntry(0)
                        if entry.hasSurfacePoint():
                            hit_p = entry.getSurfacePoint(self.nose_model)
                            hit_n = entry.getSurfaceNormal(self.nose_model)
            
            # Run Physics & Check for Contact
            contact_detected = self.deform_mesh(dt, hit_p, hit_n)

        # 3. AUDIO UPDATE
        if self.squash_sfx:
            if contact_detected:
                if self.squash_sfx.status() != self.squash_sfx.PLAYING:
                    self.squash_sfx.play()
            else:
                if self.squash_sfx.status() == self.squash_sfx.PLAYING:
                    self.squash_sfx.stop()

        return Task.cont

    def deform_mesh(self, dt, hit_p, hit_n):
        rewriter = GeomVertexRewriter(self.vdata, 'vertex')
        
        mass = 1.0
        # Use dynamic damping
        damping = self.damping_value 
        spring_k = self.recovery_speed * 5.0
        
        any_contact = False 

        i = 0
        while not rewriter.isAtEnd():
            cur_pos = rewriter.getData3()
            orig_pos = self.original_verts[i]
            velocity = self.vertex_velocities[i]
            
            ext_force = LVector3(0,0,0)
            
            # Squeezing active if VR (passive) or Mouse (Active Click AND Camera Locked)
            active_interaction = self.vr_mode_active or (self.is_squeezing and self.camera_locked)
            
            if active_interaction and hit_p:
                dist = (orig_pos - hit_p).length()
                
                # --- GAUSSIAN FORCE CALCULATION (Match nose.py) ---
                
                interaction_radius = 2.0 if self.squeeze_mode == "hard" else 4.0
                if self.vr_mode_active: interaction_radius += 1.5

                if dist < interaction_radius:
                    any_contact = True
                    
                    # 1. Gaussian Influence
                    # nose.py: sigma = radius / 3.0; influence = exp(-d^2 / 2*sigma^2)
                    sigma = interaction_radius / 3.0
                    influence = math.exp(-(dist * dist) / (2 * sigma * sigma))
                    
                    # 2. Force Direction (Always inward along normal, like nose.py)
                    # Use original normal if available, else approximate
                    if i < len(self.original_normals):
                        # nose.py uses -normal
                        push_dir = -self.original_normals[i]
                    else:
                        # Fallback (VR repel inverted = squeeze)
                        push_dir = (orig_pos - hit_p).normalized() * -1
                    
                    # 3. Apply Force
                    # Reduced multiplier to keep it stable with Gaussian peak
                    push = push_dir * (self.user_force * 1.5) * influence
                    ext_force = push

            # Physics Integration
            displacement = cur_pos - orig_pos
            spring_force = displacement * -spring_k
            damping_force = velocity * -damping
            
            accel = (ext_force + spring_force + damping_force) / mass
            new_vel = velocity + accel * dt
            new_pos = cur_pos + new_vel * dt
            
            self.vertex_velocities[i] = new_vel
            rewriter.setData3(new_pos)
            i += 1
            
        return any_contact

    def restore_immediate(self):
        if not self.vdata: return
        w = GeomVertexWriter(self.vdata, 'vertex')
        for v in self.original_verts: w.setData3(v)
        self.vertex_velocities = [LVector3(0,0,0) for _ in self.original_verts]

if __name__ == "__main__":
    app = NoseSimFinal()
    app.run()