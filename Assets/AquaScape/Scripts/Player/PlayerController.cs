using System.Collections;
using UnityEngine;
using UnityEngine.InputSystem;

namespace AquaScape
{
    // moves the player around and handles the dash, getting bumped and footsteps
    [RequireComponent(typeof(Rigidbody2D))]
    public class PlayerController : MonoBehaviour
    {
        // the one player in the scene so other scripts can find it
        public static PlayerController Instance { get; private set; }

        // input actions from the input system asset
        [Header("input")]
        public InputActionReference moveAction;
        public InputActionReference pulseAction;
        public InputActionReference dashAction;

        // how fast the player walks and how quickly they speed up and slow down
        [Header("movement")]
        public float moveSpeed = 4.6f;
        public float acceleration = 42f;
        public float deceleration = 34f;

        // dash speed, how long it lasts and the wait before the next one
        [Header("dash")]
        public float dashSpeed = 11.5f;
        public float dashDuration = 0.17f;
        public float dashCooldown = 0.65f;

        // how long the player is stunned and safe after a bump
        [Header("getting bumped")]
        public float stunTime = 0.35f;
        public float invulnerableTime = 1.3f;

        // art, animation and particle stuff
        [Header("visuals")]
        public Animator animator;
        public SpriteRenderer body;
        public Transform visual;
        public ParticleSystem dashTrail;
        public ParticleSystem footDust;

        // which way the player is looking
        public Vector2 Facing { get; private set; } = Vector2.down;
        public bool IsDashing => _dashTimer > 0f;
        // true when nothing can hurt the player
        public bool IsInvulnerable => _invulnTimer > 0f || IsDashing || _frozen;
        // total distance moved, used for stats
        public float DistanceWalked { get; private set; }
        public bool HasDashed { get; private set; }

        // animator parameter ids
        static readonly int FaceXId = Animator.StringToHash("FaceX");
        static readonly int FaceYId = Animator.StringToHash("FaceY");
        static readonly int SpeedId = Animator.StringToHash("Speed");

        Rigidbody2D _rb;
        PlayerPulse _pulse;
        Vector2 _input;
        Vector2 _dashDir;
        float _dashTimer, _dashCooldownTimer, _stunTimer, _invulnTimer;
        bool _frozen;
        Vector3 _squash = Vector3.one;

        void Awake()
        {
            Instance = this;
            _rb = GetComponent<Rigidbody2D>();
            _pulse = GetComponent<PlayerPulse>();
        }

        void OnEnable()
        {
            moveAction?.action.Enable();
            pulseAction?.action.Enable();
            dashAction?.action.Enable();
        }

        // reads input, counts down timers and updates the visuals
        void Update()
        {
            bool canAct = GameManager.Instance == null || GameManager.Instance.IsPlaying;
            canAct &= !_frozen && _stunTimer <= 0f;

            _input = canAct && moveAction != null ? moveAction.action.ReadValue<Vector2>() : Vector2.zero;
            if (_input.sqrMagnitude > 1f) _input.Normalize();

            if (canAct && dashAction != null && dashAction.action.WasPressedThisFrame())
                TryDash();
            if (canAct && pulseAction != null && pulseAction.action.WasPressedThisFrame() && _pulse != null)
                _pulse.TryPulse();

            _dashTimer -= Time.deltaTime;
            _dashCooldownTimer -= Time.deltaTime;
            _stunTimer -= Time.deltaTime;
            _invulnTimer -= Time.deltaTime;

            UpdateFacing();
            UpdateAnimator();
            UpdateVisualFeel();
        }

        // sets the velocity for dashing, being stunned or normal walking
        void FixedUpdate()
        {
            Vector2 v = _rb.linearVelocity;
            if (IsDashing)
            {
                v = _dashDir * dashSpeed;
            }
            else if (_stunTimer > 0f)
            {
                v = Vector2.MoveTowards(v, Vector2.zero, deceleration * 0.5f * Time.fixedDeltaTime);
            }
            else
            {
                Vector2 target = _input * moveSpeed;
                float rate = _input.sqrMagnitude > 0.01f ? acceleration : deceleration;
                v = Vector2.MoveTowards(v, target, rate * Time.fixedDeltaTime);
            }
            _rb.linearVelocity = v;
            DistanceWalked += v.magnitude * Time.fixedDeltaTime;
        }

        // abilities

        // starts a dash if the cooldown is done
        void TryDash()
        {
            if (_dashCooldownTimer > 0f) return;
            _dashDir = _input.sqrMagnitude > 0.01f ? _input.normalized : Facing;
            _dashTimer = dashDuration;
            _dashCooldownTimer = dashCooldown;
            HasDashed = true;
            if (dashTrail != null) dashTrail.Emit(14);
            AudioManager.Play("dash", Random.Range(0.95f, 1.05f), 1f, transform.position);
            Squash(new Vector3(1.25f, 0.8f, 1f));
        }

        // knocks the player back, like when a jellyfish hits them
        public void Bump(Vector2 from, float force)
        {
            if (IsInvulnerable) return;
            Vector2 dir = ((Vector2)transform.position - from).normalized;
            if (dir == Vector2.zero) dir = -Facing;
            _rb.linearVelocity = dir * force;
            _stunTimer = stunTime;
            _invulnTimer = invulnerableTime;
            Squash(new Vector3(0.75f, 1.25f, 1f));
            CameraFollow.Shake(0.18f, 0.3f);
        }

        // holds the player still for a few seconds
        public void Freeze(float seconds)
        {
            StartCoroutine(FreezeRoutine(seconds));
        }

        IEnumerator FreezeRoutine(float seconds)
        {
            _frozen = true;
            yield return new WaitForSeconds(seconds);
            _frozen = false;
        }

        public void SetFrozen(bool frozen) => _frozen = frozen;

        // visuals

        // picks a facing direction from the input
        void UpdateFacing()
        {
            Vector2 v = _input.sqrMagnitude > 0.01f ? _input : Vector2.zero;
            if (v == Vector2.zero) return;
            // snap to the main axis, diagonals lean toward the side view since it looks best
            Facing = Mathf.Abs(v.x) >= Mathf.Abs(v.y) * 0.8f
                ? new Vector2(Mathf.Sign(v.x), 0f)
                : new Vector2(0f, Mathf.Sign(v.y));
        }

        // sends facing and speed to the animator
        void UpdateAnimator()
        {
            if (animator == null) return;
            float speed = _rb.linearVelocity.magnitude;
            // the side clip is drawn facing right
            animator.SetFloat(FaceXId, Mathf.Abs(Facing.x));
            animator.SetFloat(FaceYId, Facing.y);
            animator.SetFloat(SpeedId, speed);
            // walk cycle plays a bit faster when moving faster
            animator.speed = speed > 0.2f ? Mathf.Lerp(0.8f, 1.25f, speed / moveSpeed) : 1f;
            if (body != null) body.flipX = Facing.x < 0f;
        }

        // eases the squash back to normal and blinks after a bump
        void UpdateVisualFeel()
        {
            if (visual == null) return;
            _squash = Vector3.Lerp(_squash, Vector3.one, Time.deltaTime * 12f);
            visual.localScale = _squash;

            // blink while invulnerable after a bump
            if (body != null)
            {
                bool blink = _invulnTimer > 0f && !IsDashing && Mathf.Repeat(Time.time * 12f, 1f) > 0.5f;
                body.color = blink ? new Color(1f, 1f, 1f, 0.45f) : Color.white;
            }
        }

        // squishes the sprite, it springs back on its own
        public void Squash(Vector3 scale) => _squash = scale;

        // called by animation events on the walk clips
        public void Footstep()
        {
            if (_rb.linearVelocity.sqrMagnitude < 0.5f) return;
            var surface = TerrainPainter.Instance != null
                ? TerrainPainter.Instance.SurfaceAt(transform.position)
                : Surface.Plaza;
            AudioManager.PlayFootstep(surface, transform.position);
            if (footDust != null) footDust.Emit(surface == Surface.Glass ? 1 : 2);
        }
    }
}
