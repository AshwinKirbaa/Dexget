import os
import shutil
import tempfile
import unittest

from jarvis.tools import filesystem as fs


class FilesystemToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jarvis_fs_test_")
        fs.ALLOWED_ROOTS = [self.tmp]

    def tearDown(self):
        fs.ALLOWED_ROOTS = None
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create_write_read_append_cycle(self):
        path = os.path.join(self.tmp, "note.txt")
        r = fs.create_file(path, "hello")
        self.assertTrue(r.success)
        r = fs.read_file(path)
        self.assertTrue(r.success)
        self.assertEqual(r.output, "hello")

        r = fs.append_file(path, " world")
        self.assertTrue(r.success)
        self.assertEqual(fs.read_file(path).output, "hello world")

        r = fs.write_file(path, "overwritten")
        self.assertTrue(r.success)
        self.assertEqual(fs.read_file(path).output, "overwritten")

    def test_create_file_refuses_if_exists(self):
        path = os.path.join(self.tmp, "dup.txt")
        self.assertTrue(fs.create_file(path, "x").success)
        r = fs.create_file(path, "y")
        self.assertFalse(r.success)
        self.assertEqual(r.error, "already_exists")

    def test_directory_create_list_search(self):
        sub = os.path.join(self.tmp, "AI Projects")
        r = fs.create_directory(sub)
        self.assertTrue(r.success)
        fs.create_file(os.path.join(sub, "README.md"), "# hi")
        listing = fs.list_directory(sub)
        self.assertTrue(listing.success)
        self.assertIn("README.md", listing.output)

        found = fs.search_files(self.tmp, "README")
        self.assertTrue(found.success)
        self.assertEqual(len(found.output), 1)

    def test_copy_move_rename(self):
        src = os.path.join(self.tmp, "a.txt")
        fs.create_file(src, "data")
        dst = os.path.join(self.tmp, "b.txt")
        self.assertTrue(fs.copy_file(src, dst).success)
        self.assertTrue(os.path.exists(src))
        self.assertTrue(os.path.exists(dst))

        moved = os.path.join(self.tmp, "c.txt")
        self.assertTrue(fs.move_file(dst, moved).success)
        self.assertFalse(os.path.exists(dst))
        self.assertTrue(os.path.exists(moved))

        r = fs.rename_file(moved, "renamed.txt")
        self.assertTrue(r.success)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "renamed.txt")))

    def test_delete_file(self):
        path = os.path.join(self.tmp, "to_delete.txt")
        fs.create_file(path, "bye")
        r = fs.delete_file(path)
        self.assertTrue(r.success)
        self.assertFalse(os.path.exists(path))

    def test_path_traversal_is_rejected(self):
        outside = tempfile.mkdtemp(prefix="jarvis_outside_")
        try:
            escape_path = os.path.join(self.tmp, "..", os.path.basename(outside), "evil.txt")
            r = fs.create_file(escape_path, "nope")
            self.assertFalse(r.success)
            self.assertEqual(r.error, "path_rejected")
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_read_missing_file(self):
        r = fs.read_file(os.path.join(self.tmp, "does_not_exist.txt"))
        self.assertFalse(r.success)
        self.assertEqual(r.error, "not_found")


if __name__ == "__main__":
    unittest.main()
