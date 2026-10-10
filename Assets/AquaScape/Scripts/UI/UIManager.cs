using System.Collections;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using UnityEngine.UI;

namespace AquaScape
{
    /// <summary>
    /// All of AquaScape's UI: title screen, HUD (bubble counter, beacon
    /// progress, objective line), toasts and hints, pause menu and the level
    /// complete screen. The widgets are created in code from a handful of
    /// glossy sprites so the whole interface shares one consistent style.
    /// </summary>
    public class UIManager : MonoBehaviour
    {
        public static UIManager Instance { get; private set; }

        [Header("Style")]
        public TMP_FontAsset font;
        public Sprite panelSprite, buttonSprite, buttonHoverSprite, pillSprite;
        public Sprite logoSprite, iconBubble, iconShard, iconBeaconOff, iconBeaconOn, completeBackground;
        public Color textDark = new Color(0.05f, 0.22f, 0.45f);
        public Color textLight = Color.white;

        CanvasGroup _title, _hud, _pause, _complete, _toast, _hint, _fade;
        TextMeshProUGUI _bubbleText, _objectiveText, _toastTitle, _toastSub, _hintText, _statsText;
        Image[] _beaconIcons;
        Image _shardIcon;
        Image[] _stars;
        Coroutine _toastRoutine, _hintRoutine;
        RectTransform _logo;

        // ------------------------------------------------------------------
        // Static helpers used by gameplay code
        // ------------------------------------------------------------------

        public static void Toast(string title, string subtitle)
        {
            if (Instance != null) Instance.ShowToast(title, subtitle);
        }

        public static void Hint(string text, float seconds)
        {
            if (Instance != null) Instance.ShowHint(text, seconds);
        }

        // ------------------------------------------------------------------
        // Setup
        // ------------------------------------------------------------------

        void Awake()
        {
            Instance = this;
            BuildCanvas();
        }

        void Start()
        {
            var gm = GameManager.Instance;
            gm.StateChanged += OnStateChanged;
            gm.BubblesChanged += _ => RefreshHud();
            gm.ShardCollected += _ => RefreshHud();
            gm.BeaconLit += _ => RefreshHud();
            if (ZoneDirector.Instance != null) ZoneDirector.Instance.ZoneEntered += OnZoneEntered;
            OnStateChanged(gm.State);
            RefreshHud();
        }

        void Update()
        {
            var gm = GameManager.Instance;
            if (gm == null) return;
            var kb = Keyboard.current;
            if (kb == null) return;

            if (kb.escapeKey.wasPressedThisFrame || kb.pKey.wasPressedThisFrame)
            {
                if (gm.State == GameState.Playing || gm.State == GameState.Paused)
                {
                    AudioManager.Play(gm.State == GameState.Playing ? "ui_open" : "ui_close");
                    gm.TogglePause();
                }
            }
            if (gm.State == GameState.Title && (kb.enterKey.wasPressedThisFrame || kb.spaceKey.wasPressedThisFrame))
                OnPlay();

            if (_logo != null && gm.State == GameState.Title)
                _logo.anchoredPosition = new Vector2(0f, 150f + Mathf.Sin(Time.unscaledTime * 1.2f) * 8f);
            if (gm.State == GameState.Playing) RefreshObjective();
        }

        void OnStateChanged(GameState s)
        {
            Show(_title, s == GameState.Title);
            Show(_hud, s == GameState.Playing || s == GameState.Paused);
            Show(_pause, s == GameState.Paused);
            Show(_complete, s == GameState.Complete);
            if (s == GameState.Complete) FillCompleteScreen();
        }

        void OnZoneEntered(int zone)
        {
            var looks = ZoneDirector.Instance.zones;
            if (zone < looks.Length) ShowToast(looks[zone].title, looks[zone].subtitle);
        }

        void OnPlay()
        {
            AudioManager.Play("ui_click");
            StartCoroutine(FadeFlash());
            GameManager.Instance.StartGame();
            GetComponent<TutorialHints>()?.Begin();
        }

        // ------------------------------------------------------------------
        // HUD
        // ------------------------------------------------------------------

        void RefreshHud()
        {
            var gm = GameManager.Instance;
            if (gm == null || _bubbleText == null) return;
            _bubbleText.text = $"{gm.Bubbles}<size=70%><color=#5d86b5> / {gm.TotalBubbles}</color></size>";
            for (int i = 0; i < _beaconIcons.Length; i++)
                _beaconIcons[i].sprite = i < gm.BeaconsLit ? iconBeaconOn : iconBeaconOff;
            int zone = ZoneDirector.Instance != null ? Mathf.Max(0, ZoneDirector.Instance.PlayerZone) : 0;
            _shardIcon.color = gm.HasShard(zone) && gm.BeaconsLit <= zone ? Color.white : new Color(1, 1, 1, 0.0f);
            StartCoroutine(Punch(_bubbleText.transform.parent));
        }

        void RefreshObjective()
        {
            var gm = GameManager.Instance;
            int zone = ZoneDirector.Instance != null ? Mathf.Max(0, ZoneDirector.Instance.PlayerZone) : 0;
            string area = ZoneDirector.Instance != null ? ZoneDirector.Instance.zones[zone].title : "";
            string goal;
            if (gm.BeaconsLit >= 3) goal = "Step into the Moonpool";
            else if (gm.BeaconsLit > zone) goal = "Cross the new bridge";
            else if (!gm.HasShard(zone)) goal = "Find the Prism Shard";
            else goal = "Pulse the Beacon with the shard";
            _objectiveText.text = $"<color=#0b5fa8>{area}</color>  ·  {goal}";
        }

        IEnumerator Punch(Transform t)
        {
            for (float k = 0; k < 0.18f; k += Time.unscaledDeltaTime)
            {
                t.localScale = Vector3.one * (1f + Mathf.Sin(k / 0.18f * Mathf.PI) * 0.12f);
                yield return null;
            }
            t.localScale = Vector3.one;
        }

        // ------------------------------------------------------------------
        // Toasts & hints
        // ------------------------------------------------------------------

        void ShowToast(string title, string sub)
        {
            _toastTitle.text = title;
            _toastSub.text = sub;
            FitWidth(_toastTitle, _toastSub, 120f, 600f);
            if (_toastRoutine != null) StopCoroutine(_toastRoutine);
            _toastRoutine = StartCoroutine(FadeInOut(_toast, 3.2f));
        }

        void ShowHint(string text, float seconds)
        {
            _hintText.text = text;
            FitWidth(_hintText, null, 110f, 420f);
            if (_hintRoutine != null) StopCoroutine(_hintRoutine);
            _hintRoutine = StartCoroutine(FadeInOut(_hint, seconds));
        }

        /// <summary>Resize a text's background panel to hug the text.</summary>
        static void FitWidth(TextMeshProUGUI a, TextMeshProUGUI b, float padding, float minWidth)
        {
            float w = a.GetPreferredValues(a.text).x;
            if (b != null && !string.IsNullOrEmpty(b.text)) w = Mathf.Max(w, b.GetPreferredValues(b.text).x);
            w = Mathf.Max(minWidth, w + padding);
            var panel = (RectTransform)a.transform.parent;
            panel.sizeDelta = new Vector2(w, panel.sizeDelta.y);
            a.rectTransform.sizeDelta = new Vector2(w - padding * 0.5f, a.rectTransform.sizeDelta.y);
            if (b != null) b.rectTransform.sizeDelta = new Vector2(w - padding * 0.5f, b.rectTransform.sizeDelta.y);
        }

        public void HideHint()
        {
            if (_hintRoutine != null) StopCoroutine(_hintRoutine);
            StartCoroutine(FadeTo(_hint, 0f, 0.3f));
        }

        IEnumerator FadeInOut(CanvasGroup g, float hold)
        {
            yield return FadeTo(g, 1f, 0.25f);
            yield return new WaitForSecondsRealtime(hold);
            yield return FadeTo(g, 0f, 0.5f);
        }

        static IEnumerator FadeTo(CanvasGroup g, float target, float seconds)
        {
            float start = g.alpha;
            for (float t = 0; t < seconds; t += Time.unscaledDeltaTime)
            {
                g.alpha = Mathf.Lerp(start, target, t / seconds);
                yield return null;
            }
            g.alpha = target;
        }

        IEnumerator FadeFlash()
        {
            _fade.alpha = 0.8f;
            yield return FadeTo(_fade, 0f, 0.8f);
        }

        void Show(CanvasGroup g, bool on)
        {
            g.gameObject.SetActive(true);
            g.interactable = on;
            g.blocksRaycasts = on;
            StartCoroutine(FadeTo(g, on ? 1f : 0f, 0.3f));
        }

        // ------------------------------------------------------------------
        // Complete screen
        // ------------------------------------------------------------------

        void FillCompleteScreen()
        {
            var gm = GameManager.Instance;
            int sec = Mathf.FloorToInt(gm.ElapsedTime);
            _statsText.text =
                $"Time    <b>{sec / 60:00}:{sec % 60:00}</b>\n" +
                $"Bubbles    <b>{gm.Bubbles} / {gm.TotalBubbles}</b>\n" +
                $"Beacons    <b>{gm.BeaconsLit} / 3</b>";
            int stars = gm.StarRating();
            for (int i = 0; i < _stars.Length; i++)
                _stars[i].color = i < stars ? new Color(1f, 0.86f, 0.35f) : new Color(1, 1, 1, 0.25f);
        }

        // ------------------------------------------------------------------
        // Widget construction
        // ------------------------------------------------------------------

        void BuildCanvas()
        {
            // Screen-space camera (not overlay) so the UI shows up in camera
            // captures/recordings and gets a touch of the bloom glow.
            var canvas = gameObject.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceCamera;
            canvas.worldCamera = Camera.main;
            canvas.planeDistance = 1f;
            canvas.sortingLayerName = "Overhead";
            canvas.sortingOrder = 100;
            var scaler = gameObject.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);
            scaler.matchWidthOrHeight = 0.5f;
            gameObject.AddComponent<GraphicRaycaster>();
            var root = (RectTransform)transform;

            // ---- HUD -------------------------------------------------------
            _hud = Group("HUD", root);
            var pill = Img("BubblePill", _hud.transform, pillSprite, new Vector2(330, 96), new Vector2(0, 1), new Vector2(40 + 165, -40 - 48));
            pill.type = Image.Type.Sliced;
            Img("BubbleIcon", pill.transform, iconBubble, new Vector2(80, 80), new Vector2(0, 0.5f), new Vector2(56, 0));
            _bubbleText = Text("Count", pill.transform, "0", 54, textDark, new Vector2(220, 80), new Vector2(0, 0.5f), new Vector2(205, 0), TextAlignmentOptions.Left);
            _shardIcon = Img("Shard", _hud.transform, iconShard, new Vector2(84, 84), new Vector2(0, 1), new Vector2(420, -88));

            var beacons = Img("BeaconPill", _hud.transform, pillSprite, new Vector2(300, 96), new Vector2(1, 1), new Vector2(-40 - 150, -40 - 48));
            beacons.type = Image.Type.Sliced;
            _beaconIcons = new Image[3];
            for (int i = 0; i < 3; i++)
                _beaconIcons[i] = Img("Beacon" + i, beacons.transform, iconBeaconOff, new Vector2(76, 76), new Vector2(0.5f, 0.5f), new Vector2(-88 + i * 88, 0));

            var obj = Img("Objective", _hud.transform, pillSprite, new Vector2(760, 70), new Vector2(0.5f, 1), new Vector2(0, -75));
            obj.type = Image.Type.Sliced;
            obj.color = new Color(1, 1, 1, 0.85f);
            _objectiveText = Text("Text", obj.transform, "", 30, textDark, new Vector2(720, 60), new Vector2(0.5f, 0.5f), Vector2.zero, TextAlignmentOptions.Center);

            // toast (centre-top) and hint (bottom)
            _toast = Group("Toast", root);
            _toast.alpha = 0f;
            var toastPanel = Img("Panel", _toast.transform, panelSprite, new Vector2(820, 170), new Vector2(0.5f, 1), new Vector2(0, -230));
            toastPanel.type = Image.Type.Sliced;
            _toastTitle = Text("Title", toastPanel.transform, "", 56, textDark, new Vector2(780, 80), new Vector2(0.5f, 0.5f), new Vector2(0, 22), TextAlignmentOptions.Center);
            _toastSub = Text("Sub", toastPanel.transform, "", 30, new Color(0.2f, 0.45f, 0.7f), new Vector2(780, 50), new Vector2(0.5f, 0.5f), new Vector2(0, -38), TextAlignmentOptions.Center);

            _hint = Group("Hint", root);
            _hint.alpha = 0f;
            var hintPanel = Img("Panel", _hint.transform, pillSprite, new Vector2(900, 84), new Vector2(0.5f, 0), new Vector2(0, 90));
            hintPanel.type = Image.Type.Sliced;
            _hintText = Text("Text", hintPanel.transform, "", 34, textDark, new Vector2(860, 70), new Vector2(0.5f, 0.5f), Vector2.zero, TextAlignmentOptions.Center);

            // ---- Title -----------------------------------------------------
            _title = Group("Title", root);
            var veil = Img("Veil", _title.transform, null, Vector2.zero, Vector2.zero, Vector2.zero);
            Stretch(veil.rectTransform);
            veil.color = new Color(0.75f, 0.93f, 1f, 0.25f);
            var logo = Img("Logo", _title.transform, logoSprite, new Vector2(1120, 336), new Vector2(0.5f, 0.5f), new Vector2(0, 150));
            logo.preserveAspect = true;
            _logo = logo.rectTransform;
            Text("Tagline", _title.transform, "a calm little adventure across the AquaScape", 34, new Color(0.08f, 0.32f, 0.6f),
                new Vector2(1200, 60), new Vector2(0.5f, 0.5f), new Vector2(0, -40), TextAlignmentOptions.Center);
            Button("Play", _title.transform, "Play", new Vector2(0, -160), OnPlay, 1.15f);
            Button("Quit", _title.transform, "Quit", new Vector2(0, -290), () => GameManager.Instance.QuitApplication());
            Text("Controls", _title.transform, "WASD / Arrows move   ·   SPACE Aqua Pulse   ·   SHIFT dash   ·   ESC pause", 26,
                new Color(0.1f, 0.3f, 0.55f), new Vector2(1400, 40), new Vector2(0.5f, 0), new Vector2(0, 60), TextAlignmentOptions.Center);

            // ---- Pause -----------------------------------------------------
            _pause = Group("Pause", root);
            var dim = Img("Dim", _pause.transform, null, Vector2.zero, Vector2.zero, Vector2.zero);
            Stretch(dim.rectTransform);
            dim.color = new Color(0.02f, 0.12f, 0.25f, 0.45f);
            var pp = Img("Panel", _pause.transform, panelSprite, new Vector2(620, 600), new Vector2(0.5f, 0.5f), Vector2.zero);
            pp.type = Image.Type.Sliced;
            Text("Title", pp.transform, "Paused", 72, textDark, new Vector2(560, 100), new Vector2(0.5f, 0.5f), new Vector2(0, 200), TextAlignmentOptions.Center);
            Button("Resume", pp.transform, "Resume", new Vector2(0, 60), () => { AudioManager.Play("ui_close"); GameManager.Instance.TogglePause(); });
            Button("Restart", pp.transform, "Restart", new Vector2(0, -60), () => GameManager.Instance.Restart());
            Button("Title", pp.transform, "Title Screen", new Vector2(0, -180), () => GameManager.Instance.QuitToTitle());

            // ---- Complete ----------------------------------------------------
            _complete = Group("Complete", root);
            var bg = Img("Background", _complete.transform, completeBackground, Vector2.zero, Vector2.zero, Vector2.zero);
            Stretch(bg.rectTransform);
            bg.color = completeBackground != null ? Color.white : new Color(0.05f, 0.08f, 0.3f, 0.8f);
            var cp = Img("Panel", _complete.transform, panelSprite, new Vector2(760, 720), new Vector2(0.5f, 0.5f), Vector2.zero);
            cp.type = Image.Type.Sliced;
            Text("Title", cp.transform, "Level Complete!", 76, textDark, new Vector2(720, 110), new Vector2(0.5f, 0.5f), new Vector2(0, 250), TextAlignmentOptions.Center);
            Text("Sub", cp.transform, "The Moonpool glows again.", 32, new Color(0.2f, 0.45f, 0.7f), new Vector2(720, 50), new Vector2(0.5f, 0.5f), new Vector2(0, 180), TextAlignmentOptions.Center);
            _stars = new Image[3];
            for (int i = 0; i < 3; i++)
                _stars[i] = Img("Star" + i, cp.transform, iconShard, new Vector2(90, 90), new Vector2(0.5f, 0.5f), new Vector2(-110 + i * 110, 95));
            _statsText = Text("Stats", cp.transform, "", 40, textDark, new Vector2(620, 170), new Vector2(0.5f, 0.5f), new Vector2(0, -40), TextAlignmentOptions.Center);
            _statsText.lineSpacing = 18;
            Button("Again", cp.transform, "Play Again", new Vector2(0, -190), () => GameManager.Instance.Restart());
            Button("Title", cp.transform, "Title Screen", new Vector2(0, -300), () => GameManager.Instance.QuitToTitle(), 0.85f);

            // full-screen white flash used for transitions
            _fade = Group("Flash", root);
            var flash = Img("White", _fade.transform, null, Vector2.zero, Vector2.zero, Vector2.zero);
            Stretch(flash.rectTransform);
            flash.color = new Color(0.9f, 0.98f, 1f, 1f);
            flash.raycastTarget = false;
            _fade.alpha = 0f;
            _fade.blocksRaycasts = false;

            foreach (var g in new[] { _hud, _pause, _complete, _title }) g.alpha = 0f;
        }

        CanvasGroup Group(string name, RectTransform parent)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(CanvasGroup));
            var rt = (RectTransform)go.transform;
            rt.SetParent(parent, false);
            Stretch(rt);
            return go.GetComponent<CanvasGroup>();
        }

        static void Stretch(RectTransform rt)
        {
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = rt.offsetMax = Vector2.zero;
        }

        static Image Img(string name, Transform parent, Sprite sprite, Vector2 size, Vector2 anchor, Vector2 pos)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Image));
            var rt = (RectTransform)go.transform;
            rt.SetParent(parent, false);
            rt.anchorMin = rt.anchorMax = anchor;
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = size;
            rt.anchoredPosition = pos;
            var img = go.GetComponent<Image>();
            img.sprite = sprite;
            img.raycastTarget = false;
            return img;
        }

        TextMeshProUGUI Text(string name, Transform parent, string text, float size, Color color, Vector2 box,
            Vector2 anchor, Vector2 pos, TextAlignmentOptions align)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(TextMeshProUGUI));
            var rt = (RectTransform)go.transform;
            rt.SetParent(parent, false);
            rt.anchorMin = rt.anchorMax = anchor;
            rt.sizeDelta = box;
            rt.anchoredPosition = pos;
            var t = go.GetComponent<TextMeshProUGUI>();
            if (font != null) t.font = font;
            t.text = text;
            t.fontSize = size;
            t.color = color;
            t.alignment = align;
            t.raycastTarget = false;
            t.textWrappingMode = TextWrappingModes.NoWrap;
            return t;
        }

        void Button(string name, Transform parent, string label, Vector2 pos, UnityEngine.Events.UnityAction onClick, float scale = 1f)
        {
            var img = Img(name, parent, buttonSprite, new Vector2(440, 104) * scale, new Vector2(0.5f, 0.5f), pos);
            img.type = Image.Type.Sliced;
            img.raycastTarget = true;
            var b = img.gameObject.AddComponent<UnityEngine.UI.Button>();
            b.transition = Selectable.Transition.SpriteSwap;
            b.spriteState = new SpriteState { highlightedSprite = buttonHoverSprite, selectedSprite = buttonHoverSprite, pressedSprite = buttonHoverSprite };
            b.onClick.AddListener(onClick);
            var txt = Text("Label", img.transform, label, 44 * scale, textLight, img.rectTransform.sizeDelta, new Vector2(0.5f, 0.5f), new Vector2(0, 2), TextAlignmentOptions.Center);
            txt.fontStyle = FontStyles.Bold;
            txt.outlineWidth = 0.18f;
            txt.outlineColor = new Color32(20, 110, 190, 255);
            img.gameObject.AddComponent<ButtonFX>();
        }
    }

}
