using System.Collections.ObjectModel;
using System.Collections.Specialized;
using System.ComponentModel;

namespace VNText.Studio.App.Models;

/// <summary>
/// ObservableCollection that can mutate silently then fire a single Reset.
/// </summary>
internal sealed class ResettableObservableCollection<T> : ObservableCollection<T>
{
    private bool _suppress;

    protected override void OnCollectionChanged(NotifyCollectionChangedEventArgs e)
    {
        if (!_suppress)
            base.OnCollectionChanged(e);
    }

    protected override void OnPropertyChanged(PropertyChangedEventArgs e)
    {
        if (!_suppress)
            base.OnPropertyChanged(e);
    }

    public void BeginSilentUpdate() => _suppress = true;

    public void EndSilentUpdate()
    {
        _suppress = false;
        OnPropertyChanged(new PropertyChangedEventArgs(nameof(Count)));
        OnPropertyChanged(new PropertyChangedEventArgs("Item[]"));
        OnCollectionChanged(new NotifyCollectionChangedEventArgs(NotifyCollectionChangedAction.Reset));
    }

    public void AddSilent(T item) => Items.Add(item);

    public void ClearSilentThenNotify()
    {
        var was = _suppress;
        _suppress = true;
        try
        {
            Items.Clear();
        }
        finally
        {
            _suppress = was;
        }
        if (!_suppress)
        {
            OnPropertyChanged(new PropertyChangedEventArgs(nameof(Count)));
            OnPropertyChanged(new PropertyChangedEventArgs("Item[]"));
            OnCollectionChanged(new NotifyCollectionChangedEventArgs(NotifyCollectionChangedAction.Reset));
        }
    }
}
