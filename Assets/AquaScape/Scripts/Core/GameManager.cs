using System;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace AquaScape
{
    // the main states the game can be in
    public enum GameState { Title, Playing, Paused, Complete }

    // runs the game flow and keeps track of bubbles, shards, beacons and the timer
    public class GameManager : MonoBehaviour
    {
        public static GameManager Instance { get; private set; }

        // set before a reload so we skip the title screen
        static bool s_skipTitle;

        // how many zones the level has
        public const int ZoneCount = 3;

        // current state and player progress
        public GameState State { get; private set; } = GameState.Title;
        public bool IsPlaying => State == GameState.Playing;
        public int Bubbles { get; private set; }
        public int TotalBubbles { get; private set; }
        public float ElapsedTime { get; private set; }
        public int BeaconsLit { get; private set; }

        readonly bool[] _hasShard = new bool[ZoneCount];

        // events other scripts listen to
        public event Action<GameState> StateChanged;
        // sends the new bubble count
        public event Action<int> BubblesChanged;
        // sends the zone index
        public event Action<int> ShardCollected;
        // sends the zone index
        public event Action<int> BeaconLit;

        void Awake()
        {
            Instance = this;
            // count every bubble in the level including the ones inside clams
            // done in awake so the hud gets the right total in start
            TotalBubbles = FindObjectsByType<Bubble>().Length;
            foreach (var clam in FindObjectsByType<BubbleClam>())
                TotalBubbles += clam.BubbleCount;
        }

        // go to play or title depending on how the scene was loaded
        void Start()
        {
            SetState(s_skipTitle ? GameState.Playing : GameState.Title);
            s_skipTitle = false;
        }

        // run timer only counts while playing
        void Update()
        {
            if (State == GameState.Playing)
                ElapsedTime += Time.deltaTime;
        }

        // flow

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

        // reload the level and start playing right away
        public void Restart()
        {
            s_skipTitle = true;
            ReloadScene();
        }

        // reload the level and show the title screen
        public void QuitToTitle()
        {
            s_skipTitle = false;
            ReloadScene();
        }

        // quits the game or stops play mode in the editor
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

        // changes state, freezes time when paused and tells listeners
        void SetState(GameState next)
        {
            State = next;
            Time.timeScale = next == GameState.Paused ? 0f : 1f;
            StateChanged?.Invoke(next);
        }

        // progress

        // adds bubbles but never goes below zero
        public void AddBubbles(int amount)
        {
            Bubbles = Mathf.Max(0, Bubbles + amount);
            BubblesChanged?.Invoke(Bubbles);
        }

        // takes away up to amount bubbles and returns how many were lost
        public int LoseBubbles(int amount)
        {
            int lost = Mathf.Min(amount, Bubbles);
            if (lost > 0) AddBubbles(-lost);
            return lost;
        }

        public bool HasShard(int zone) => _hasShard[zone];

        // marks the shard for this zone as picked up
        public void CollectShard(int zone)
        {
            _hasShard[zone] = true;
            ShardCollected?.Invoke(zone);
        }

        // called when a beacon gets lit
        public void NotifyBeaconLit(int zone)
        {
            BeaconsLit++;
            BeaconLit?.Invoke(zone);
        }

        // star rating for the end screen based on bubbles collected
        public int StarRating()
        {
            float ratio = TotalBubbles > 0 ? (float)Bubbles / TotalBubbles : 1f;
            if (ratio >= 0.95f) return 3;
            if (ratio >= 0.6f) return 2;
            return 1;
        }
    }
}
