using System.Collections;
using UnityEngine;

namespace AquaScape
{
    /// <summary>
    /// Teaches the controls at the start of the level, one hint at a time, and
    /// moves on as soon as the player has actually tried each thing.
    /// </summary>
    public class TutorialHints : MonoBehaviour
    {
        bool _started;

        public void Begin()
        {
            if (_started) return;
            _started = true;
            StartCoroutine(Run());
        }

        void Start()
        {
            // restarting skips the title screen, so start straight away
            if (GameManager.Instance != null && GameManager.Instance.State == GameState.Playing) Begin();
        }

        IEnumerator Run()
        {
            var player = PlayerController.Instance;
            var pulse = player != null ? player.GetComponent<PlayerPulse>() : null;
            var gm = GameManager.Instance;
            yield return new WaitForSeconds(1.2f);

            UIManager.Hint("Move with  <b>WASD</b>  or the  <b>Arrow Keys</b>", 30f);
            yield return new WaitUntil(() => player.DistanceWalked > 3f);

            UIManager.Hint("Collect the floating bubbles", 30f);
            yield return new WaitUntil(() => gm.Bubbles >= 2);

            UIManager.Hint("Press  <b>SPACE</b>  to send an Aqua Pulse. It opens clams and powers crystals", 30f);
            yield return new WaitUntil(() => pulse.PulseCount > 0);

            UIManager.Hint("Tap  <b>SHIFT</b>  to dash", 30f);
            float t = 0f;
            yield return new WaitUntil(() => player.HasDashed || (t += Time.deltaTime) > 8f);

            UIManager.Hint("Find each area's  <b>Prism Shard</b>  and use it to light the Beacon", 6f);
        }
    }
}
