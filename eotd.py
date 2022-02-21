"""Example code for the epd2in13bc driver."""
import argparse
import logging
from time import sleep
from typing import Dict

import requests
from emoji.unicode_codes import EMOJI_UNICODE_ENGLISH
from PIL import Image

from einkd.display import Display
from einkd.drivers.base import BaseDriver
from einkd.gui.components import ImageComponent, TextComponent
from einkd.gui.window import Window

LOGGER = logging.getLogger(__name__)


class EOTDException(Exception):
    """A problem occurred."""


class EmojiOfTheDay:
    """Display the Emoj of the Day on the display!."""

    def __init__(
        self,
        display: Display,
        eotd_api: str,
        *,
        poll_interval: int = 2,
    ) -> None:
        self._display = display
        self._eotd_api = eotd_api
        self._poll_interval = poll_interval

        self._layout = Window(
            width=display.width,
            height=display.height,
            components={
                (0, 0): ImageComponent(
                    "a", cell_x=4, cell_y=10, image=Image.new("1", (100, 100)),
                ),
                (4, 0): ImageComponent(
                    "b", cell_x=4, cell_y=10, image=Image.new("1", (100, 100)),
                ),
                (8, 0): ImageComponent(
                    "c", cell_x=4, cell_y=10, image=Image.new("1", (100, 100)),
                ),
                (0, 10): TextComponent("message", cell_y=2, text="")
            }
        )

        self._error_layout = Window(
            width=display.width,
            height=display.height,
            components={
                (0, 0): TextComponent("message", cell_y=6, text="An error occurred."),
                (0, 6): TextComponent("error", cell_y=6, text="Unknown"),
            }
        )

    def run(self) -> None:
        """The main loop for the program."""
        error = False
        info: Dict[str, str] = {}

        # Loop, only changing the display if needed.
        while True:
            try:
                new_info = self.get_info()
                if info != new_info or error:
                    LOGGER.info("Emojis changed!")
                    info = new_info
                    self.display_emoji(info)
                error = False
            except EOTDException as e:
                if not error:
                    self._display_error(e)
                    error = True

            # To save CPU time, wait a few seconds
            sleep(self._poll_interval)

    def get_image(self, emoji: str, *, style: str = "apple") -> Image.Image:
        """
        Get an image of a given emoji.

        Fetches the image over HTTPS from an emoji CDN.

        :param emoji: The name of the emoji to fetch, in english.
        :param style: The style of the emoji to fetch.
        :returns: An Image.Image of the emoji, usually a PNG.
        :raises EOTDException: There was a problem getting the emoji.
        """
        # First, look up the emoji.
        try:
            emoji_char = EMOJI_UNICODE_ENGLISH[emoji]
        except KeyError:
            raise EOTDException(f"Unknown emoji: {emoji}")

        # Fetch the emoji from the emoji CDN
        try:
            resp = requests.get(
                f"https://emojicdn.elk.sh/{emoji_char}?style=apple",
                stream=1,
            )
            resp.raise_for_status()
        except Exception as e:
            LOGGER.error(f"Exception: {e}")
            raise EOTDException("Error when contacting emoji API.")

        return Image.open(resp.raw)

    def display_emoji(self, info: Dict[str, str]) -> None:
        """
        Display the emoji in the info on the screen.

        :param info: The info to display.
        :raises EOTDException: Info was not valid.
        """
        try:
            a, b, c = info["a"], info["b"], info["c"]
            message = info["message"]
        except KeyError as e:
            LOGGER.error(f"Exception: {e}")
            raise EOTDException("Unable to find all values in JSON.")

        LOGGER.info(f"Updating display: {a}, {b}, {c} ({message})")

        self._layout.components[(0, 0)].image = self.get_image(a)  # type: ignore
        self._layout.components[(4, 0)].image = self.get_image(b)  # type: ignore
        self._layout.components[(8, 0)].image = self.get_image(c)  # type: ignore
        self._layout.components[(0, 10)].text = message  # type: ignore

        self._display.show(self._layout.draw())
        self._display.refresh()

    def get_info(self) -> Dict[str, str]:
        """
        Get the raw info from the EOTD API.

        :returns: A dictionary of values.
        :raises EOTDException: Unable to fetch data from the API.
        """
        try:
            resp = requests.get(self._eotd_api)
            resp.raise_for_status()
            return resp.json()  # type: ignore
        except Exception as e:
            LOGGER.error(e)
            raise EOTDException("Unable to fetch from API")

    def _display_error(self, e: Exception) -> None:
        """Display an exception on the display."""
        self._error_layout.components[(0, 6)].text = str(e)  # type: ignore
        self._display.show(self._error_layout.draw())
        self._display.refresh()


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("url")
    parser.add_argument(
        "--display", default="tk", const="tk", nargs="?", choices=["epd2in13", "tk"],
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # Dynamically choose the display driver
    driver: BaseDriver
    if args.display == "epd2in13":
        from einkd.drivers.epd2in13bc import EPD2in13bcDriver
        driverr = EPD2in13bcDriver()
    elif args.display == "tk":
        from einkd.drivers.virtual import TkinterDriver
        driver = TkinterDriver((400, 200))
    else:
        raise RuntimeError("No driver defined.")

    with driver as epd:
        epd.clear()
        eotd = EmojiOfTheDay(epd, args.url)
        eotd.run()
