using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace AquaScape
{
    // a glass puzzle block that slides away from the player when pulsed
    // it stops at water, walls, other cubes or props, and pressure pads catch it
    // if it gets pulsed twice while stuck it goes back to its start
    [RequireComponent(typeof(Rigidbody2D))]
    public class GlassCube : PulseTarget
    {
        // every cube in the scene
        public static readonly List<GlassCube> Cubes = new List<GlassCube>();

        public float slideSpeed = 9f;
        // farthest the cube can slide in one push
        public int maxSlideCells = 12;
        public SpriteRenderer sprite;

        // true once the cube is stuck on a pad
        public bool Locked { get; private set; }
        // the grid cell the cube is in
        public Vector3Int Cell => TerrainPainter.Instance.WorldToCell(_rb.position);

        Rigidbody2D _rb;
        Vector3 _home;
        bool _moving;
        int _blockedPulses;

        public override bool ShowsPrompt => !Locked && !_moving;

        void Awake()
        {
            _rb = GetComponent<Rigidbody2D>();
            _rb.bodyType = RigidbodyType2D.Kinematic;
            _home = transform.position;
        }

        protected override void OnEnable() { base.OnEnable(); Cubes.Add(this); }
        protected override void OnDisable() { base.OnDisable(); Cubes.Remove(this); }

        // pushes the cube along the main axis away from the pulse
        public override void OnPulse(Vector2 origin)
        {
            if (Locked || _moving) return;
            Vector2 d = (Vector2)transform.position - origin;
            Vector3Int dir = Mathf.Abs(d.x) >= Mathf.Abs(d.y)
                ? new Vector3Int(d.x >= 0 ? 1 : -1, 0, 0)
                : new Vector3Int(0, d.y >= 0 ? 1 : -1, 0);

            Vector3Int target = FindSlideTarget(Cell, dir, out var pad);
            if (target == Cell)
            {
                _blockedPulses++;
                if (_blockedPulses >= 2) StartCoroutine(ResetRoutine());
                else StartCoroutine(Nudge(dir));
                return;
            }
            _blockedPulses = 0;
            StartCoroutine(SlideRoutine(target, pad));
        }

        // steps cell by cell in a direction until the next cell is blocked
        Vector3Int FindSlideTarget(Vector3Int start, Vector3Int dir, out PressurePad pad)
        {
            pad = null;
            var cell = start;
            for (int i = 0; i < maxSlideCells; i++)
            {
                var next = cell + dir;
                if (IsBlocked(next)) break;
                cell = next;
                pad = PressurePad.At(cell);
                // pads catch cubes
                if (pad != null && !pad.Pressed) break;
                pad = null;
            }
            return cell;
        }

        // checks if a cell has water, a cube or something solid in it
        bool IsBlocked(Vector3Int c)
        {
            var terrain = TerrainPainter.Instance;
            if (!terrain.IsWalkable(c)) return true;
            foreach (var other in Cubes)
                if (other != this && other.Cell == c) return true;
            // any other solid collider in that cell like props, gates or the player
            Vector2 center = TerrainPainter.CellCenter(c);
            var hits = Physics2D.OverlapBoxAll(center, new Vector2(0.7f, 0.7f), 0f);
            foreach (var h in hits)
            {
                if (h.isTrigger || h.attachedRigidbody == _rb) continue;
                // water edge is already handled above
                if (h.GetComponentInParent<TerrainPainter>() != null) continue;
                return true;
            }
            return false;
        }

        // slides the cube to the target cell and presses the pad if there is one
        IEnumerator SlideRoutine(Vector3Int target, PressurePad pad)
        {
            _moving = true;
            AudioManager.Play("cube_push", Random.Range(0.95f, 1.05f), 1f, transform.position);
            Vector2 end = TerrainPainter.CellCenter(target);
            while ((_rb.position - end).sqrMagnitude > 0.0001f)
            {
                _rb.MovePosition(Vector2.MoveTowards(_rb.position, end, slideSpeed * Time.fixedDeltaTime));
                yield return new WaitForFixedUpdate();
            }
            _rb.position = end;
            CameraFollow.Shake(0.04f, 0.1f);
            if (sprite != null) StartCoroutine(Wobble());
            _moving = false;
            if (pad != null)
            {
                Locked = true;
                pad.Press(this);
            }
        }

        // small bump animation when the cube cant move
        IEnumerator Nudge(Vector3Int dir)
        {
            AudioManager.Play("beacon_denied", 1.4f, 0.6f, transform.position);
            Vector3 basePos = sprite.transform.localPosition;
            for (float t = 0; t < 0.2f; t += Time.deltaTime)
            {
                sprite.transform.localPosition = basePos + (Vector3)dir * Mathf.Sin(t / 0.2f * Mathf.PI) * 0.08f;
                yield return null;
            }
            sprite.transform.localPosition = basePos;
        }

        // poofs the cube back to where it started
        IEnumerator ResetRoutine()
        {
            _moving = true;
            _blockedPulses = 0;
            AudioManager.Play("cube_reset", 1f, 1f, transform.position);
            GameAssets.Burst(GameAssets.Instance != null ? GameAssets.Instance.poofFx : null, transform.position + Vector3.up * 0.5f);
            yield return Scale(1f, 0f, 0.2f);
            _rb.position = _home;
            transform.position = _home;
            GameAssets.Burst(GameAssets.Instance != null ? GameAssets.Instance.poofFx : null, _home + Vector3.up * 0.5f);
            yield return Scale(0f, 1f, 0.25f);
            _moving = false;
            UIManager.Hint("The cube was stuck, so it returned to its start", 3f);
        }

        // scales the sprite between two sizes over time
        IEnumerator Scale(float from, float to, float seconds)
        {
            for (float t = 0; t < seconds; t += Time.deltaTime)
            {
                sprite.transform.localScale = Vector3.one * Mathf.Lerp(from, to, t / seconds);
                yield return null;
            }
            sprite.transform.localScale = Vector3.one * to;
        }

        // little jiggle after the cube stops
        IEnumerator Wobble()
        {
            for (float t = 0; t < 0.3f; t += Time.deltaTime)
            {
                float k = t / 0.3f;
                float s = 1f + Mathf.Sin(k * Mathf.PI * 3f) * 0.08f * (1f - k);
                sprite.transform.localScale = new Vector3(s, 2f - s, 1f);
                yield return null;
            }
            sprite.transform.localScale = Vector3.one;
        }
    }
}
