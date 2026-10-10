using System.Collections;
using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace AquaScape
{
    // the level exit, it wakes up after the last beacon and ends the level when you step in
    public class MoonpoolPortal : MonoBehaviour
    {
        public SpriteRenderer sprite;
        public Sprite activeSprite;
        public Light2D glow;
        public ParticleSystem motes;
        // how close the player has to be to go in
        public float enterRadius = 0.9f;

        public bool Active { get; private set; }
        bool _entered;

        // turns the portal on, only works once
        public void Activate()
        {
            if (Active) return;
            Active = true;
            StartCoroutine(AwakenRoutine());
        }

        // shows the portal on camera and fades its glow in
        IEnumerator AwakenRoutine()
        {
            yield return new WaitForSeconds(0.6f);
            CameraFollow.Focus(transform.position, 2f);
            yield return new WaitForSeconds(0.4f);
            AudioManager.Play("portal_open", 1f, 1f, transform.position);
            sprite.sprite = activeSprite;
            if (motes != null) motes.Play();
            for (float t = 0; t < 1.2f; t += Time.deltaTime)
            {
                if (glow != null) glow.intensity = Mathf.Lerp(0f, 2.2f, t / 1.2f);
                yield return null;
            }
            UIManager.Hint("Step into the Moonpool", 4f);
        }

        // pulses the glow and checks if the player stepped in
        void Update()
        {
            if (Active && glow != null && !_entered)
                glow.intensity = 2.0f + Mathf.Sin(Time.time * 2.5f) * 0.3f;
            if (sprite != null && Active)
                sprite.transform.localScale = Vector3.one * (1f + Mathf.Sin(Time.time * 2f) * 0.015f);

            if (!Active || _entered) return;
            var player = PlayerController.Instance;
            if (player == null) return;
            if (Vector2.Distance(player.transform.position, transform.position) < enterRadius)
                StartCoroutine(EnterRoutine(player));
        }

        // spins the player down into the pool and finishes the level
        IEnumerator EnterRoutine(PlayerController player)
        {
            _entered = true;
            player.SetFrozen(true);
            AudioManager.Play("portal_enter", 1f, 1f, transform.position);
            GameAssets.Burst(GameAssets.Instance != null ? GameAssets.Instance.sparkleFx : null, transform.position + Vector3.up * 0.3f);

            // spiral the player down into the pool
            Vector3 start = player.transform.position;
            Transform vis = player.visual;
            for (float t = 0; t < 1.3f; t += Time.deltaTime)
            {
                float k = t / 1.3f;
                player.transform.position = Vector3.Lerp(start, transform.position, k);
                if (vis != null)
                {
                    vis.localScale = Vector3.one * (1f - k * k);
                    vis.localRotation = Quaternion.Euler(0, 0, k * 540f);
                }
                if (glow != null) glow.intensity = 2.2f + k * 3f;
                yield return null;
            }
            if (vis != null) vis.gameObject.SetActive(false);
            yield return new WaitForSeconds(0.4f);
            GameManager.Instance?.CompleteLevel();
        }
    }
}
