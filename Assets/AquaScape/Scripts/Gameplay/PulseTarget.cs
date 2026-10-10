using System.Collections.Generic;
using UnityEngine;

namespace AquaScape
{
    /// <summary>
    /// Base class for anything that reacts to the player's Aqua Pulse.
    /// Targets register themselves in a static list so the pulse (and the
    /// on-screen prompt) can find them without physics queries.
    /// </summary>
    public abstract class PulseTarget : MonoBehaviour
    {
        public static readonly List<PulseTarget> All = new List<PulseTarget>();

        [Tooltip("Where the floating SPACE prompt appears, relative to the pivot.")]
        public Vector3 promptOffset = new Vector3(0f, 1.6f, 0f);
        [Tooltip("Extra pulse reach for big objects.")]
        public float reachBonus = 0f;

        /// <summary>True while pulsing this object would do something useful.</summary>
        public virtual bool ShowsPrompt => true;

        public abstract void OnPulse(Vector2 origin);

        protected virtual void OnEnable() => All.Add(this);
        protected virtual void OnDisable() => All.Remove(this);
    }
}
