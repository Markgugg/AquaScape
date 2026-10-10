using System;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace AquaScape
{
    public enum GameState { Title, Playing, Paused, Complete }

    /// <summary>
    /// Owns the overall game flow (title -> playing -> paused -> complete) and the
    /// player's progress: bubbles collected, prism shards carried, beacons lit and
    /// the run timer. Other systems listen to its events instead of polling.
    /// </summary>
    public class GameManager : MonoBehaviour
    {
        public static GameManager Instance { get; private set; }

        /// <summary>Set before reloading the scene to jump straight into play.</summary>
        static bool s_skipTitle;

        public const int ZoneCount = 3;

        public GameState State { get; private set; } = GameState.Title;
        public bool IsPlaying => State == GameState.Playing;
        public int Bubbles { get; private set; }
        public int TotalBubbles { get; private set; }
        public float ElapsedTime { get; private set; }
        public int BeaconsLit { get; private set; }

        readonly bool[] _hasShard = new bool[ZoneCount];

        public event Action<GameState> StateChanged;
        public event Action<int> BubblesChanged;          // new bubble count
        public event Action<int> ShardCollected;          // zone index
        public event Action<int> BeaconLit;               // zone index

        void Awake()
        {
            Instance = this;
        }

        void Start()
        {
            // Every bubble that can ever be collected counts toward the total
            // (loose bubbles plus the ones hidden inside clams).
            TotalBubbles = FindObjectsByType<Bubble>().Length;
            foreach (var clam in FindObjectsByType<BubbleClam>())
                TotalBubbles += clam.BubbleCount;

            SetState(s_skipTitle ? GameState.Playing : GameState.Title);
            s_skipTitle = false;
        }

        void Update()
        {
            if (State == GameState.Playing)
                ElapsedTime += Time.deltaTime;
        }

        // ------------------------------------------------------------------
        // Flow
        // ------------------------------------------------------------------

        public void StartGame()
        {
            if (State == GameState.Title) SetState(GameState.Playing);
        }

        public void TogglePause()
        {
            if (State == GameState.Playing) SetState(GameState.Paused);
            else if (State == GameState.Paused) SetState(GameState.Playing);
        }

        public void CompleteLevel()
        {
            if (State == GameState.Playing) SetState(GameState.Complete);
        }

        /// <summary>Reload the level and start playing immediately.</summary>
        public void Restart()
        {
            s_skipTitle = true;
            ReloadScene();
        }

        /// <summary>Reload the level and show the title screen.</summary>
        public void QuitToTitle()
        {
            s_skipTitle = false;
            ReloadScene();
        }

        public void QuitApplication()
        {
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#else
            Application.Quit();
#endif
        }

        static void ReloadScene()
        {
            Time.timeScale = 1f;
            SceneManager.LoadScene(SceneManager.GetActiveScene().buildIndex);
        }

        void SetState(GameState next)
        {
            State = next;
            Time.timeScale = next == GameState.Paused ? 0f : 1f;
            StateChanged?.Invoke(next);
        }

        // ------------------------------------------------------------------
        // Progress
        // ------------------------------------------------------------------

        public void AddBubbles(int amount)
        {
            Bubbles = Mathf.Max(0, Bubbles + amount);
            BubblesChanged?.Invoke(Bubbles);
        }

        /// <summary>Removes up to `amount` bubbles and returns how many were lost.</summary>
        public int LoseBubbles(int amount)
        {
            int lost = Mathf.Min(amount, Bubbles);
            if (lost > 0) AddBubbles(-lost);
            return lost;
        }

        public bool HasShard(int zone) => _hasShard[zone];

        public void CollectShard(int zone)
        {
            _hasShard[zone] = true;
            ShardCollected?.Invoke(zone);
        }

        public void NotifyBeaconLit(int zone)
        {
            BeaconsLit++;
            BeaconLit?.Invoke(zone);
        }

        /// <summary>A simple star rating for the completion screen.</summary>
        public int StarRating()
        {
            float ratio = TotalBubbles > 0 ? (float)Bubbles / TotalBubbles : 1f;
            if (ratio >= 0.95f) return 3;
            if (ratio >= 0.6f) return 2;
            return 1;
        }
    }
}
