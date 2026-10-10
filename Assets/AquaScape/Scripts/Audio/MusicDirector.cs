using UnityEngine;

namespace AquaScape
{
    // music that adds layers as you light beacons
    // all stems start at the same time so they stay in sync
    // pad and night pad are always on, keys come in after beacon 1,
    // arp after beacon 2 and melody after beacon 3
    // ambience loops crossfade by zone
    public class MusicDirector : MonoBehaviour
    {
        [Header("music stems")]
        // all stems need to be the same length
        public AudioClip pad;
        public AudioClip nightPad;
        public AudioClip keys;
        public AudioClip arp;
        public AudioClip melody;
        public AudioClip completeJingle;

        [Header("ambience")]
        public AudioClip oceanAmbience;
        public AudioClip cityAmbience;
        public AudioClip nightAmbience;

        [Header("mix")]
        [Range(0f, 1f)] public float musicVolume = 0.55f;
        [Range(0f, 1f)] public float ambienceVolume = 0.5f;
        // how long a layer takes to fade in or out
        public float layerFadeSeconds = 3f;

        AudioSource _pad, _night, _keys, _arp, _melody;
        AudioSource _ocean, _city, _nightAmb, _jingle;
        bool _complete;

        // makes all the loops and schedules them to start together
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

        // makes a silent looping source for a clip
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

        // plays the jingle once when the level is done
        void OnStateChanged(GameState state)
        {
            if (state == GameState.Complete && !_complete)
            {
                _complete = true;
                if (completeJingle != null) _jingle.PlayOneShot(completeJingle, 0.9f);
            }
        }

        // fades each layer toward its target volume
        void Update()
        {
            var gm = GameManager.Instance;
            int beacons = gm != null ? gm.BeaconsLit : 0;
            var state = gm != null ? gm.State : GameState.Playing;
            float night = ZoneDirector.Instance != null ? ZoneDirector.Instance.Night : 0f;
            float city = ZoneDirector.Instance != null ? ZoneDirector.Instance.City : 0f;

            // music gets quieter while paused and under the end jingle
            float master = musicVolume;
            if (state == GameState.Paused) master *= 0.35f;
            if (_complete) master *= _jingle.isPlaying ? 0.25f : 0.8f;

            // title screen only plays the pad so the first beacon feels like a lift
            bool playing = state != GameState.Title;
            Fade(_pad, master * (1f - night));
            Fade(_night, master * night);
            Fade(_keys, master * (playing && beacons >= 1 ? 0.85f : 0f));
            Fade(_arp, master * (playing && beacons >= 2 ? 0.75f : 0f));
            Fade(_melody, master * ((playing && beacons >= 3) || _complete ? 0.8f : 0f));

            // ambience crossfades between ocean, city and night
            float amb = ambienceVolume * (state == GameState.Paused ? 0.5f : 1f);
            Fade(_ocean, amb * (1f - city) * (1f - night), 1.5f);
            Fade(_city, amb * city * (1f - night), 1.5f);
            Fade(_nightAmb, amb * night, 1.5f);
        }

        // moves a source volume toward a target
        void Fade(AudioSource src, float target, float seconds = -1f)
        {
            if (src == null || src.clip == null) return;
            if (seconds < 0f) seconds = layerFadeSeconds;
            // unscaled so fades keep working while the game is paused
            src.volume = Mathf.MoveTowards(src.volume, target, Time.unscaledDeltaTime / seconds);
        }
    }
}
