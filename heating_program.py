from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


MIN_TEMPERATURE = 5.0
MAX_TEMPERATURE = 35.0
DEFAULT_STORAGE_PATH = Path(__file__).with_name("heating_devices.json")
DEVICE_FIELDS = {
    "name",
    "kind",
    "is_on",
    "current_temperature",
    "target_temperature",
}


@dataclass
class HeatingDevice:
    name: str
    kind: str
    is_on: bool = False
    current_temperature: float | None = None
    target_temperature: float | None = None


class HeatingProgram:
    def __init__(self, storage_path: str | Path = DEFAULT_STORAGE_PATH) -> None:
        self.storage_path = Path(storage_path)
        self.devices: dict[str, HeatingDevice] = {}
        self.load()

    def load(self) -> None:
        if not self.storage_path.exists():
            return

        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise TypeError("Główny obiekt JSON musi być słownikiem.")
            devices = data.get("devices", [])
            if not isinstance(devices, list):
                raise TypeError("Pole 'devices' musi być listą.")
            loaded_devices: dict[str, HeatingDevice] = {}
            for item in devices:
                if not isinstance(item, dict):
                    raise TypeError("Każde urządzenie musi być obiektem JSON.")
                if "name" not in item or "kind" not in item:
                    raise TypeError("Urządzenie musi zawierać pola 'name' i 'kind'.")
                self._validate_device_payload(item)
                filtered_item = {
                    key: value
                    for key, value in item.items()
                    if key in DEVICE_FIELDS
                }
                device = HeatingDevice(**filtered_item)
                if device.current_temperature is not None:
                    self._validate_temperature(device.current_temperature)
                if device.target_temperature is not None:
                    self._validate_temperature(device.target_temperature)
                if device.name in loaded_devices:
                    raise ValueError(
                        f"Zduplikowana nazwa urządzenia '{device.name}' w pliku."
                    )
                loaded_devices[device.name] = device
            self.devices = loaded_devices
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                "Nie można odczytać pliku z urządzeniami grzewczymi."
            ) from exc

    def save(self) -> None:
        payload = {
            "devices": [asdict(device) for device in self.devices.values()],
        }
        parent_directory = self.storage_path.parent
        parent_directory.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=parent_directory,
            delete=False,
        ) as temp_file:
            temp_file.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            temp_path = Path(temp_file.name)

        os.replace(temp_path, self.storage_path)

    def add_device(
        self,
        name: str,
        kind: str,
        current_temperature: float | None = None,
        target_temperature: float | None = None,
    ) -> HeatingDevice:
        if name in self.devices:
            raise ValueError(f"Urządzenie '{name}' już istnieje.")
        if current_temperature is not None:
            self._validate_temperature(current_temperature)
        if target_temperature is not None:
            self._validate_temperature(target_temperature)

        device = HeatingDevice(
            name=name,
            kind=kind,
            current_temperature=current_temperature,
            target_temperature=target_temperature,
        )
        self.devices[name] = device
        self.save()
        return device

    def set_power(self, name: str, is_on: bool) -> HeatingDevice:
        device = self.get_device(name)
        device.is_on = is_on
        self.save()
        return device

    def set_target_temperature(
        self,
        name: str,
        target_temperature: float,
    ) -> HeatingDevice:
        self._validate_temperature(target_temperature)
        device = self.get_device(name)
        device.target_temperature = target_temperature
        self.save()
        return device

    def get_device(self, name: str) -> HeatingDevice:
        try:
            return self.devices[name]
        except KeyError as exc:
            raise ValueError(f"Nie znaleziono urządzenia '{name}'.") from exc

    def list_devices(self) -> list[HeatingDevice]:
        return sorted(self.devices.values(), key=lambda device: device.name.casefold())

    @staticmethod
    def _validate_temperature(temperature: float) -> None:
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
            raise ValueError("Temperatura musi być liczbą.")
        if not MIN_TEMPERATURE <= temperature <= MAX_TEMPERATURE:
            raise ValueError(
                f"Temperatura musi być w zakresie "
                f"{MIN_TEMPERATURE}-{MAX_TEMPERATURE}°C."
            )

    @staticmethod
    def _validate_device_payload(item: dict[str, object]) -> None:
        if not isinstance(item["name"], str) or not item["name"]:
            raise TypeError("Pole 'name' musi być niepustym napisem.")
        if not isinstance(item["kind"], str) or not item["kind"]:
            raise TypeError("Pole 'kind' musi być niepustym napisem.")
        if "is_on" in item and not isinstance(item["is_on"], bool):
            raise TypeError("Pole 'is_on' musi być wartością logiczną.")
        for field_name in ("current_temperature", "target_temperature"):
            value = item.get(field_name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                raise TypeError(f"Pole '{field_name}' musi być liczbą lub null.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Program do obsługi urządzeń grzewczych.",
    )
    parser.add_argument(
        "--storage",
        default=str(DEFAULT_STORAGE_PATH),
        help="Ścieżka do pliku z zapisanymi urządzeniami.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Dodaje urządzenie.")
    add_parser.add_argument("name", help="Nazwa urządzenia.")
    add_parser.add_argument("kind", help="Typ urządzenia.")
    add_parser.add_argument(
        "--current-temperature",
        type=float,
        default=None,
        help="Aktualna temperatura urządzenia lub pomieszczenia.",
    )
    add_parser.add_argument(
        "--target-temperature",
        type=float,
        default=None,
        help="Temperatura docelowa.",
    )

    power_parser = subparsers.add_parser("on", help="Włącza urządzenie.")
    power_parser.add_argument("name", help="Nazwa urządzenia.")

    power_parser = subparsers.add_parser("off", help="Wyłącza urządzenie.")
    power_parser.add_argument("name", help="Nazwa urządzenia.")

    set_parser = subparsers.add_parser(
        "set-temperature",
        help="Ustawia temperaturę docelową.",
    )
    set_parser.add_argument("name", help="Nazwa urządzenia.")
    set_parser.add_argument("temperature", type=float, help="Temperatura docelowa.")

    subparsers.add_parser("list", help="Wyświetla wszystkie urządzenia.")

    return parser


def format_device(device: HeatingDevice) -> str:
    power_state = "włączone" if device.is_on else "wyłączone"
    current_temperature = (
        f"{device.current_temperature:.1f}°C"
        if device.current_temperature is not None
        else "brak"
    )
    target_temperature = (
        f"{device.target_temperature:.1f}°C"
        if device.target_temperature is not None
        else "brak"
    )
    return (
        f"{device.name} ({device.kind}) - stan: {power_state}, "
        f"aktualna: {current_temperature}, docelowa: {target_temperature}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        program = HeatingProgram(Path(args.storage))
        if args.command == "add":
            device = program.add_device(
                args.name,
                args.kind,
                args.current_temperature,
                args.target_temperature,
            )
            print(f"Dodano urządzenie: {format_device(device)}")
        elif args.command == "on":
            device = program.set_power(args.name, True)
            print(f"Urządzenie włączone: {format_device(device)}")
        elif args.command == "off":
            device = program.set_power(args.name, False)
            print(f"Urządzenie wyłączone: {format_device(device)}")
        elif args.command == "set-temperature":
            device = program.set_target_temperature(args.name, args.temperature)
            print(f"Zmieniono temperaturę: {format_device(device)}")
        elif args.command == "list":
            devices = program.list_devices()
            if not devices:
                print("Brak skonfigurowanych urządzeń grzewczych.")
            else:
                for device in devices:
                    print(format_device(device))
    except ValueError as exc:
        parser.exit(status=1, message=f"Błąd: {exc}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
