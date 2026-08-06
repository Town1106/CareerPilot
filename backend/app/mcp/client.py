from abc import ABC, abstractmethod


class MCPClient(ABC):
    """MCP 客户端基类，定义工具发现与调用的统一接口。"""

    def __init__(self) -> None:
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...