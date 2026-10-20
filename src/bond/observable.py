from typing import Callable


class Observable[T]:
    def __init__(self, value: T):
        self._value: T = value
        self._subscribers: list[Callable[[T], None]] = []

    def subscribe(self, subscriber: Callable[[T], None]):
        self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber: Callable[[T], None]):
        self._subscribers.remove(subscriber)

    def notify(self):
        for subscriber in self._subscribers:
            subscriber(self._value)

    def clear_subscribers(self):
        self._subscribers.clear()

    def is_subscribed(self, subscriber: Callable[[T], None]):
        return subscriber in self._subscribers

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, new_value: T):
        self._value = new_value
        self.notify()
