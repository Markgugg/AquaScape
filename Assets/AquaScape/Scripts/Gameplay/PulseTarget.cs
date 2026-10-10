using System.Collections.Generic;
using UnityEngine;

namespace AquaScape
{
    // base class for anything that reacts to the player pulse
    // targets add themselves to a list so the pulse can find them without physics
    public abstract class PulseTarget : MonoBehaviour
    {
        // every active pulse target
        public static readonly List<PulseTarget> All = new List<PulseTarget>();

        // where the space prompt floats compared to the object
        public Vector3 promptOffset = new Vector3(0f, 1.6f, 0f);
        // extra pulse reach for big objects
        public float reachBonus = 0f;

        // true when pulsing this would actually do something
        public virtual bool ShowsPrompt => true;

        // what happens when the pulse hits this
        public abstract void OnPulse(Vector2 origin);

        protected virtual void OnEnable() => All.Add(this);
        protected virtual void OnDisable() => All.Remove(this);
    }
}
