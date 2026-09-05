import contextlib
import io
import tempfile
import unittest
from pathlib import Path
import json

from heating_program import HeatingProgram, MAX_TEMPERATURE, MIN_TEMPERATURE, main


class HeatingProgramTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self.temp_dir.name) / "devices.json"
        self.program = HeatingProgram(self.storage_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_add_device_saves_it(self) -> None:
        device = self.program.add_device(
            "Kocioł",
            "piec",
            current_temperature=19.5,
            target_temperature=21.0,
        )

        self.assertEqual("Kocioł", device.name)
        self.assertTrue(self.storage_path.exists())
        reloaded = HeatingProgram(self.storage_path)
        self.assertEqual(["Kocioł"], [item.name for item in reloaded.list_devices()])

    def test_add_device_creates_missing_parent_directories(self) -> None:
        nested_storage_path = Path(self.temp_dir.name) / "nested" / "devices.json"
        nested_program = HeatingProgram(nested_storage_path)

        nested_program.add_device("Kotłownia", "piec")

        self.assertTrue(nested_storage_path.exists())

    def test_set_power_changes_device_state(self) -> None:
        self.program.add_device("Salon", "grzejnik")

        device = self.program.set_power("Salon", True)

        self.assertTrue(device.is_on)

    def test_add_device_validates_current_temperature_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "Temperatura musi być w zakresie"):
            self.program.add_device(
                "Garaż",
                "nagrzewnica",
                current_temperature=MAX_TEMPERATURE + 1,
            )

    def test_set_target_temperature_validates_allowed_range(self) -> None:
        self.program.add_device("Łazienka", "podłogówka")

        with self.assertRaisesRegex(ValueError, "Temperatura musi być w zakresie"):
            self.program.set_target_temperature("Łazienka", MIN_TEMPERATURE - 0.5)

        with self.assertRaisesRegex(ValueError, "Temperatura musi być w zakresie"):
            self.program.set_target_temperature("Łazienka", MAX_TEMPERATURE + 0.5)

    def test_set_target_temperature_rejects_boolean_value(self) -> None:
        self.program.add_device("Łazienka", "podłogówka")

        with self.assertRaisesRegex(ValueError, "Temperatura musi być liczbą"):
            self.program.set_target_temperature("Łazienka", True)

    def test_add_device_validates_target_temperature_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "Temperatura musi być w zakresie"):
            self.program.add_device(
                "Sypialnia",
                "grzejnik",
                target_temperature=MAX_TEMPERATURE + 1,
            )

    def test_unknown_device_raises_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Nie znaleziono urządzenia"):
            self.program.set_power("Nieznane", True)

    def test_invalid_storage_file_raises_readable_error(self) -> None:
        self.storage_path.write_text("{broken json", encoding="utf-8")

        with self.assertRaisesRegex(
            ValueError,
            "Nie można odczytać pliku z urządzeniami grzewczymi",
        ):
            HeatingProgram(self.storage_path)

    def test_non_object_storage_root_raises_readable_error(self) -> None:
        self.storage_path.write_text("[]", encoding="utf-8")

        with self.assertRaisesRegex(
            ValueError,
            "Nie można odczytać pliku z urządzeniami grzewczymi",
        ):
            HeatingProgram(self.storage_path)

    def test_duplicate_device_names_in_storage_raise_error(self) -> None:
        self.storage_path.write_text(
            """
            {
              "devices": [
                {"name": "Salon", "kind": "grzejnik"},
                {"name": "Salon", "kind": "piec"}
              ]
            }
            """.strip(),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            ValueError,
            "Nie można odczytać pliku z urządzeniami grzewczymi",
        ):
            HeatingProgram(self.storage_path)

    def test_storage_ignores_unsupported_device_fields(self) -> None:
        self.storage_path.write_text(
            """
            {
              "devices": [
                {"name": "Salon", "kind": "grzejnik", "unsupported": true}
              ]
            }
            """.strip(),
            encoding="utf-8",
        )

        program = HeatingProgram(self.storage_path)
        program.save()

        self.assertEqual(["Salon"], [device.name for device in program.list_devices()])
        saved_data = json.loads(self.storage_path.read_text(encoding="utf-8"))
        self.assertEqual(
            [{"name": "Salon", "kind": "grzejnik", "is_on": False, "current_temperature": None, "target_temperature": None}],
            saved_data["devices"],
        )

    def test_storage_rejects_out_of_range_temperatures(self) -> None:
        self.storage_path.write_text(
            """
            {
              "devices": [
                {"name": "Salon", "kind": "grzejnik", "target_temperature": 40}
              ]
            }
            """.strip(),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            ValueError,
            "Nie można odczytać pliku z urządzeniami grzewczymi",
        ):
            HeatingProgram(self.storage_path)

    def test_storage_rejects_invalid_field_types(self) -> None:
        self.storage_path.write_text(
            """
            {
              "devices": [
                {"name": 123, "kind": [], "is_on": "yes"}
              ]
            }
            """.strip(),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            ValueError,
            "Nie można odczytać pliku z urządzeniami grzewczymi",
        ):
            HeatingProgram(self.storage_path)

    def test_main_lists_empty_storage(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = main(["--storage", str(self.storage_path), "list"])

        self.assertEqual(0, exit_code)
        self.assertEqual(
            "Brak skonfigurowanych urządzeń grzewczych.",
            stdout.getvalue().strip(),
        )

    def test_main_adds_and_lists_device(self) -> None:
        add_stdout = io.StringIO()
        list_stdout = io.StringIO()

        with contextlib.redirect_stdout(add_stdout):
            add_exit_code = main(
                [
                    "--storage",
                    str(self.storage_path),
                    "add",
                    "Kocioł",
                    "piec",
                    "--target-temperature",
                    "21",
                ]
            )
        with contextlib.redirect_stdout(list_stdout):
            list_exit_code = main(["--storage", str(self.storage_path), "list"])

        self.assertEqual(0, add_exit_code)
        self.assertEqual(0, list_exit_code)
        self.assertIn("Dodano urządzenie:", add_stdout.getvalue())
        self.assertIn("Kocioł (piec)", list_stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
