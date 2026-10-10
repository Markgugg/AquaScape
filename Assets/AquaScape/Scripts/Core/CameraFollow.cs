using System.Collections;
using UnityEngine;

namespace AquaScape
{
    // smooth follow camera with look ahead, level bounds, screen shake,
    // a slow title screen pan and short focus shots on other spots
    [RequireComponent(typeof(Camera))]
    public class CameraFollow : MonoBehaviour
    {
        public static CameraFollow Instance { get; private set; }

        // what the camera follows and how smooth it is
        public Transform target;
        public float smoothTime = 0.22f;
        public float lookAhead = 1.2f;
        // world area the camera view has to stay inside
        public Rect bounds = new Rect(0, 0, 120, 32);
        // above this y the camera lifts up to show the horizon
        public float horizonLiftStart = 23f;
        public float horizonLift = 3.5f;

        [Header("title screen pan")]
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

        // start on the title spot or right on the player
        void Start()
        {
            if (target != null) _targetBody = target.GetComponent<Rigidbody2D>();
            if (GameManager.Instance != null && GameManager.Instance.State == GameState.Title)
                SnapTo(titleFrom);
            else if (target != null)
                SnapTo(target.position);
        }

        // jumps the camera straight to a point
        void SnapTo(Vector2 p)
        {
            var c = Clamp(p);
            transform.position = new Vector3(c.x, c.y, transform.position.z);
        }

        // picks where the camera wants to be and moves toward it
        void LateUpdate()
        {
            var state = GameManager.Instance != null ? GameManager.Instance.State : GameState.Playing;
            Vector2 desired;

            if (state == GameState.Title)
            {
                // slow back and forth drift behind the title screen
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
                // near the north shore lift the view so the horizon shows
                float lift = Mathf.Clamp01((target.position.y - horizonLiftStart) / 6f);
                desired.y += Mathf.SmoothStep(0f, 1f, lift) * horizonLift;
            }
            else return;

            desired = Clamp(desired);
            Vector3 pos = Vector3.SmoothDamp(transform.position,
                new Vector3(desired.x, desired.y, transform.position.z), ref _velocity,
                _focus.HasValue ? 0.45f : smoothTime);

            transform.position = pos + (Vector3)ShakeOffset();
        }

        // random offset for screen shake that fades out
        Vector2 ShakeOffset()
        {
            if (_shakeTime <= 0f) return Vector2.zero;
            _shakeTime -= Time.unscaledDeltaTime;
            // shake gets smaller as the time runs out
            float k = Mathf.Clamp01(_shakeTime / _shakeDuration);
            return Random.insideUnitCircle * _shakeAmp * k;
        }

        // keeps the camera view inside the level bounds
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

        // small screen shake, amplitude is in world units
        public static void Shake(float amplitude, float duration)
        {
            if (Instance == null) return;
            // dont let a weaker shake cancel a stronger one
            if (amplitude < Instance._shakeAmp * Mathf.Clamp01(Instance._shakeTime / Mathf.Max(0.01f, Instance._shakeDuration))) return;
            Instance._shakeAmp = amplitude;
            Instance._shakeDuration = Instance._shakeTime = duration;
        }

        // pans to a point for a bit then goes back to the player
        public static void Focus(Vector2 point, float seconds)
        {
            if (Instance == null) return;
            Instance.StopAllCoroutines();
            Instance.StartCoroutine(Instance.FocusRoutine(point, seconds));
        }

        // holds the focus point for some seconds
        IEnumerator FocusRoutine(Vector2 point, float seconds)
        {
            _focus = point;
            yield return new WaitForSeconds(seconds);
            _focus = null;
        }
    }
}
