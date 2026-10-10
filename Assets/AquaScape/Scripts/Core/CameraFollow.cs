using System.Collections;
using UnityEngine;

namespace AquaScape
{
    /// <summary>
    /// Smooth follow camera with velocity look-ahead, level bounds, screen shake,
    /// a slow drifting pan for the title screen, and short "focus" shots that
    /// show the player something happening elsewhere (e.g. a bridge forming).
    /// </summary>
    [RequireComponent(typeof(Camera))]
    public class CameraFollow : MonoBehaviour
    {
        public static CameraFollow Instance { get; private set; }

        public Transform target;
        public float smoothTime = 0.22f;
        public float lookAhead = 1.2f;
        [Tooltip("World-space rectangle the camera view must stay inside.")]
        public Rect bounds = new Rect(0, 0, 120, 32);

        [Header("Title screen pan")]
        public Vector2 titleFrom = new Vector2(8, 14);
        public Vector2 titleTo = new Vector2(26, 16);
        public float titlePanSeconds = 30f;

        Camera _cam;
        Vector3 _velocity;
        Vector2 _look;
        float _shakeAmp, _shakeTime, _shakeDuration;
        Vector2? _focus;
        Rigidbody2D _targetBody;

        void Awake()
        {
            Instance = this;
            _cam = GetComponent<Camera>();
        }

        void Start()
        {
            if (target != null) _targetBody = target.GetComponent<Rigidbody2D>();
            if (GameManager.Instance != null && GameManager.Instance.State == GameState.Title)
                SnapTo(titleFrom);
            else if (target != null)
                SnapTo(target.position);
        }

        void SnapTo(Vector2 p)
        {
            var c = Clamp(p);
            transform.position = new Vector3(c.x, c.y, transform.position.z);
        }

        void LateUpdate()
        {
            var state = GameManager.Instance != null ? GameManager.Instance.State : GameState.Playing;
            Vector2 desired;

            if (state == GameState.Title)
            {
                // gentle ping-pong drift across the lagoon behind the title UI
                float t = Mathf.PingPong(Time.time / titlePanSeconds, 1f);
                desired = Vector2.Lerp(titleFrom, titleTo, Mathf.SmoothStep(0, 1, t));
            }
            else if (_focus.HasValue)
            {
                desired = _focus.Value;
            }
            else if (target != null)
            {
                Vector2 vel = _targetBody != null ? _targetBody.linearVelocity : Vector2.zero;
                Vector2 lookTarget = Vector2.ClampMagnitude(vel * 0.25f, 1f) * lookAhead;
                _look = Vector2.Lerp(_look, lookTarget, Time.deltaTime * 2.5f);
                desired = (Vector2)target.position + _look + Vector2.up * 0.4f;
            }
            else return;

            desired = Clamp(desired);
            Vector3 pos = Vector3.SmoothDamp(transform.position,
                new Vector3(desired.x, desired.y, transform.position.z), ref _velocity,
                _focus.HasValue ? 0.45f : smoothTime);

            transform.position = pos + (Vector3)ShakeOffset();
        }

        Vector2 ShakeOffset()
        {
            if (_shakeTime <= 0f) return Vector2.zero;
            _shakeTime -= Time.unscaledDeltaTime;
            float k = Mathf.Clamp01(_shakeTime / _shakeDuration);
            float a = _shakeAmp * k * k;
            float t = Time.unscaledTime * 38f;
            return new Vector2(Mathf.PerlinNoise(t, 0.3f) - 0.5f, Mathf.PerlinNoise(0.7f, t) - 0.5f) * 2f * a;
        }

        Vector2 Clamp(Vector2 p)
        {
            float halfH = _cam.orthographicSize;
            float halfW = halfH * _cam.aspect;
            float minX = bounds.xMin + halfW, maxX = bounds.xMax - halfW;
            float minY = bounds.yMin + halfH, maxY = bounds.yMax - halfH;
            p.x = minX > maxX ? bounds.center.x : Mathf.Clamp(p.x, minX, maxX);
            p.y = minY > maxY ? bounds.center.y : Mathf.Clamp(p.y, minY, maxY);
            return p;
        }

        /// <summary>Small screen shake; amplitude in world units.</summary>
        public static void Shake(float amplitude, float duration)
        {
            if (Instance == null) return;
            if (amplitude < Instance._shakeAmp * Mathf.Clamp01(Instance._shakeTime / Mathf.Max(0.01f, Instance._shakeDuration))) return;
            Instance._shakeAmp = amplitude;
            Instance._shakeDuration = Instance._shakeTime = duration;
        }

        /// <summary>Pan to a point for a moment, then return to the player.</summary>
        public static void Focus(Vector2 point, float seconds)
        {
            if (Instance == null) return;
            Instance.StopAllCoroutines();
            Instance.StartCoroutine(Instance.FocusRoutine(point, seconds));
        }

        IEnumerator FocusRoutine(Vector2 point, float seconds)
        {
            _focus = point;
            yield return new WaitForSeconds(seconds);
            _focus = null;
        }
    }
}
