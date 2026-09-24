namespace EmbrAIon.Reference.Unity
{
    public sealed class CounterState
    {
        public CounterState(int initialValue = 0)
        {
            Value = initialValue;
        }

        public int Value { get; private set; }

        public int Increment()
        {
            Value++;
            return Value;
        }

        public void Reset(int value = 0)
        {
            Value = value;
        }
    }
}
