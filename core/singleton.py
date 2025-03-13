from typing import ClassVar


class SingletonMeta(type):
    """
    В Python класс Одиночка можно реализовать по-разному. Возможные способы
    включают себя базовый класс, декоратор, метакласс. Мы воспользуемся
    метаклассом, поскольку он лучше всего подходит для этой цели.
    """  # noqa: RUF002

    _instances: ClassVar[dict[type["SingletonMeta"], "SingletonMeta"]] = {}

    def __call__(cls, *args: object, **kwargs: object) -> "SingletonMeta":
        """
        Данная реализация не учитывает возможное изменение передаваемых
        аргументов в `__init__`.
        """
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]
