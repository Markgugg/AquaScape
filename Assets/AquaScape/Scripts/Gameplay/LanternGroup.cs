using System.Collections.Generic;
using UnityEngine;

namespace AquaScape
{
    // builds a bridge once every lantern in the group is lit
    public class LanternGroup : MonoBehaviour
    {
        public List<MoonLantern> lanterns = new List<MoonLantern>();
        // the bridge that appears when all lanterns are lit
        public BridgeBuilder bridge;

        // how many lanterns are lit right now
        public int LitCount
        {
            get
            {
                int n = 0;
                foreach (var l in lanterns) if (l.IsLit) n++;
                return n;
            }
        }

        // called by a lantern when it lights, shows progress or builds the bridge
        public void OnLanternLit()
        {
            int lit = LitCount;
            if (lit < lanterns.Count)
            {
                UIManager.Hint($"Moon lanterns lit: {lit} / {lanterns.Count}", 2.5f);
                return;
            }
            UIManager.Toast("The moon path appears", "All lanterns are glowing");
            bridge?.Activate(0.8f);
        }
    }
}
