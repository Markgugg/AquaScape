using UnityEngine;

namespace AquaScape
{
    /// <summary>
    /// Adaptive soundtrack. All music stems share the same length and start on
    /// the same DSP tick so they stay in sync; each one is faded in or out
    /// depending on what the player has achieved:
    ///   pad / night pad : always on (crossfaded by how far into the night we are)
    ///   keys            : after the first beacon is lit
    ///   arpeggio        : after the second beacon
    ///   melody          : after the third beacon
    /// Ambience loops are crossfaded by zone.
    /// </summary>
    public class MusicDirector : MonoBehaviour
    {
        [Header("Music stems (identical length)")]
        public AudioClip pad;
        public AudioClip nightPad;
        public AudioClip keys;
        public AudioClip arp;
        public AudioClip melody;
        public AudioClip completeJingle;

        [Header("Ambience")]
        public AudioClip oceanAmbience;
        public AudioClip cityAmbience;
        public AudioClip nightAmbience;

        [Header("Mix")]
        [Range(0f, 1f)] public float musicVolume = 0.55f;
        [Range(0f, 1f)] public float ambienceVolume = 0.5f;
        public float layerFadeSeconds = 3f;

        AudioSource _pad, _night, _keys, _arp, _melody;
        AudioSource _ocean, _city, _nightAmb, _jingle;
        bool _complete;

        void Start()
        {
            double start = AudioSettings.dspTime + 0.2;
            _pad = CreateLoop(pad, start);
            _night = CreateLoop(nightPad, start);
            _keys = CreateLoop(keys, start);
            _arp = CreateLoop(arp, start);
            _melody = CreateLoop(melody, start);
            _ocean = CreateLoop(oceanAmbience, start);
            _city = CreateLoop(cityAmbience, start);
            _nightAmb = CreateLoop(nightAmbience, start);
            _jingle = gameObject.AddComponent<AudioSource>();
            _jingle.playOnAwake = false;

            if (GameManager.Instance != null)
                GameManager.Instance.StateChanged += OnStateChanged;
        }

        void OnDestroy()
        {
            if (GameManager.Instance != null)
                GameManager.Instance.StateChanged -= OnStateChanged;
        }

        AudioSource CreateLoop(AudioClip clip, double dspStart)
        {
            var src = gameObject.AddComponent<AudioSource>();
            src.clip = clip;
            src.loop = true;
            src.volume = 0f;
            src.playOnAwake = false;
            src.ignoreListenerPause = true;
            if (clip != null) src.PlayScheduled(dspStart);
            return src;
        }

        void OnStateChanged(GameState state)
        {
            if (state == GameState.Complete && !_complete)
            {
                _complete = true;
                if (completeJingle != null) _jingle.PlayOneShot(completeJingle, 0.9f);
            }
        }

        void Update()
        {
            var gm = GameManager.Instance;
            int beacons = gm != null ? gm.BeaconsLit : 0;
            var state = gm != null ? gm.State : GameState.Playing;
            float night = ZoneDirector.Instance != null ? ZoneDirector.Instance.Night : 0f;
            float city = ZoneDirector.Instance != null ? ZoneDirector.Instance.City : 0f;

            // Music ducks while paused and dips under the completion jingle.
            float master = musicVolume;
            if (state == GameState.Paused) master *= 0.35f;
            if (_complete) master *= _jingle.isPlaying ? 0.25f : 0.8f;

            // Title screen: just the base pad so the first beacon is a noticeable lift.
            bool playing = state != GameState.Title;
            Fade(_pad, master * (1f - night));
            Fade(_night, master * night);
            Fade(_keys, master * (playing && beacons >= 1 ? 0.85f : 0f));
            Fade(_arp, master * (playing && beacons >= 2 ? 0.75f : 0f));
            Fade(_melody, master * ((playing && beacons >= 3) || _complete ? 0.8f : 0f));

            float amb = ambienceVolume * (state == GameState.Paused ? 0.5f : 1f);
            Fade(_ocean, amb * (1f - city) * (1f - night), 1.5f);
            Fade(_city, amb * city * (1f - night), 1.5f);
            Fade(_nightAmb, amb * night, 1.5f);
        }

        void Fade(AudioSource src, float target, float seconds = -1f)
        {
            if (src == null || src.clip == null) return;
            if (seconds < 0f) seconds = layerFadeSeconds;
            // unscaled so fades keep working while the game is paused
            src.volume = Mathf.MoveTowards(src.volume, target, Time.unscaledDeltaTime / seconds);
        }
    }
}
