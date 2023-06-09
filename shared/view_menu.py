from typing import TypeAlias, List

from discord import Interaction, Embed

from shared.buttons_menu import ButtonsMenu

PageType: TypeAlias = tuple[str, Embed | List[Embed]]


class ViewMenu:
    def __init__(self, interaction: Interaction, pages: List[PageType]):
        self.interaction = interaction
        self.pages = pages
        self._page = 0
        self._actual_page: PageType = self.pages[0]
        self._view = ButtonsMenu(owner=interaction.user, buttons=[{'label': page[0]} for page in self.pages])
        self._view.callback = self.__view_callback
        self._view.update_callback = self.update

    async def __view_callback(self, index, *args):
        self._page = index
        self._actual_page = self.pages[index]
        await self.update()

    async def start(self):
        message_args = {'embeds' if isinstance(self._actual_page[1], list) else 'embed': self._actual_page[1],
                        'view': self._view}
        await self.interaction.response.send_message(**message_args)

    async def update(self):
        message_args = {'embeds' if isinstance(self._actual_page[1], list) else 'embed': self._actual_page[1],
                        'view': self._view}
        await self.interaction.edit_original_response(**message_args)
