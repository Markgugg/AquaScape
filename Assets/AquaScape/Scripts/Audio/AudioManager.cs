using System.Collections.Generic;
using UnityEngine;

namespace AquaScape
{
    public enum Surface { Plaza, Grass, Glass }

    /// <summary>
    /// Plays one-shot sound effects from a small pool of AudioSources.
    /// Clips are looked up by id (e.g. "pulse", "gate_open"). Sounds emitted in
    /// the world are panned slightly left/right relative to the camera.
    /// </summary>
    public class AudioManager : MonoBehaviour
    {
        [System.Serializable]
        public class NamedClip
        {
            public string id;
            public AudioClip clip;
            [Range(0f, 1.5f)] public float volume = 1f;
        }

        public static AudioManager Instance { get; private set; }

        [Header("Clip library")]
        public List<NamedClip> clips = new List<NamedClip>();
        public AudioClip[] footstepPlaza;
        public AudioClip[] footstepGrass;
        public AudioClip[] footstepGlass;
        [Tooltip("Ascending pentatonic notes, played in order while collecting quickly.")]
        public AudioClip[] bubbleNotes;

        [Header("Mix")]
        [Range(0f, 1f)] public float sfxVolume = 0.9f;
        [Range(0f, 1f)] public float footstepVolume = 0.45f;
        public float bubbleComboWindow = 0.9f;
        public int poolSize = 16;

        readonly Dictionary<string, NamedClip> _lookup = new Dictionary<string, NamedClip>();
        AudioSource[] _pool;
        int _next;
        int _bubbleCombo;
        float _lastBubbleTime = -10f;
        int _lastFootstep = -1;

        void Awake()
        {
            Instance = this;
            foreach (var c in clips)
                if (c.clip != null) _lookup[c.id] = c;

            _pool = new AudioSource[poolSize];
            for (int i = 0; i < poolSize; i++)
            {
                var src = gameObject.AddComponent<AudioSource>();
                src.playOnAwake = false;
                src.spatialBlend = 0f;
                _pool[i] = src;
            }
        }

        // ------------------------------------------------------------------
        // Static convenience API (safe to call when no manager exists)
        // ------------------------------------------------------------------

        public static void Play(string id, float pitch = 1f, float volume = 1f, Vector3? worldPos = null)
        {
            if (Instance == null || !Instance._lookup.TryGetValue(id, out var nc)) return;
            Instance.PlayClip(nc.clip, nc.volume * volume, pitch, worldPos);
        }

        public static void PlayFootstep(Surface surface, Vector3 pos)
        {
            if (Instance == null) return;
            var set = surface == Surface.Grass ? Instance.footstepGrass
                    : surface == Surface.Glass ? Instance.footstepGlass
                    : Instance.footstepPlaza;
            if (set == null || set.Length == 0) return;

            // never repeat the same sample twice in a row
            int i = Random.Range(0, set.Length);
            if (set.Length > 1 && i == Instance._lastFootstep) i = (i + 1) % set.Length;
            Instance._lastFootstep = i;
            Instance.PlayClip(set[i], Instance.footstepVolume, Random.Range(0.94f, 1.06f), pos);
        }

        /// <summary>Collecting bubbles in quick succession climbs the scale.</summary>
        public static void PlayBubbleNote(Vector3 pos)
        {
            var am = Instance;
            if (am == null || am.bubbleNotes == null || am.bubbleNotes.Length == 0) return;
            if (Time.time - am._lastBubbleTime > am.bubbleComboWindow) am._bubbleCombo = 0;
            am._lastBubbleTime = Time.time;
            int note = Mathf.Min(am._bubbleCombo, am.bubbleNotes.Length - 1);
            am._bubbleCombo++;
            am.PlayClip(am.bubbleNotes[note], 0.8f, 1f, pos);
        }

        void PlayClip(AudioClip clip, float volume, float pitch, Vector3? worldPos)
        {
            if (clip == null) return;
            var src = _pool[_next];
            _next = (_next + 1) % _pool.Length;
            src.clip = clip;
            src.volume = volume * sfxVolume;
            src.pitch = pitch;
            src.panStereo = worldPos.HasValue ? PanFor(worldPos.Value) : 0f;
            src.Play();
        }

        static float PanFor(Vector3 pos)
        {
            var cam = Camera.main;
            if (cam == null) return 0f;
            float half = cam.orthographicSize * cam.aspect;
            return Mathf.Clamp((pos.x - cam.transform.position.x) / half, -1f, 1f) * 0.45f;
        }
    }
}
