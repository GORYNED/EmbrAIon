using UnityEngine;

namespace EmbrAIon.Reference.Unity
{
    public sealed class CounterController : MonoBehaviour
    {
        [SerializeField] private int initialValue;

        private CounterState _state;

        public int Value => _state?.Value ?? initialValue;

        private void Awake()
        {
            _state = new CounterState(initialValue);
        }

        public void Increment()
        {
            _state ??= new CounterState(initialValue);
            _state.Increment();
        }

        public void ResetCounter()
        {
            _state ??= new CounterState(initialValue);
            _state.Reset(initialValue);
        }
    }
}
