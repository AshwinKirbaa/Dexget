import os
import unittest
from jarvis.command_parser import parse_compound_command
from jarvis.router import _try_filesystem, _try_system_info
from jarvis.router import RouteType

class TestCoreComponents(unittest.TestCase):
    def test_parser(self):
        cmd = "open discord, join Hangout voice call and turn camera on"
        parsed = parse_compound_command(cmd)
        self.assertEqual(parsed.primary_intent, "application_workflow")
        self.assertEqual(parsed.target_application, "Discord")
        self.assertEqual(parsed.environment, "desktop")
        
        cmd = "open calculator and do 2+2"
        parsed = parse_compound_command(cmd)
        self.assertEqual(parsed.primary_intent, "application_workflow")
        self.assertEqual(parsed.target_application, "Calculator")
        self.assertEqual(parsed.environment, "desktop")
        self.assertEqual(parsed.workflow_steps[1].parameters["expression"], "2+2")
        
    def test_filesystem_router(self):
        # Drive letter
        res = _try_filesystem("open D:")
        if res:
            self.assertEqual(res.route_type, RouteType.FILESYSTEM)
            self.assertEqual(res.tool_args["intent"], "DRIVE_OPEN")
            self.assertEqual(res.tool_args["location"], "D:\\")
            
        # Drive word
        res = _try_filesystem("open drive d")
        if res:
            self.assertEqual(res.route_type, RouteType.FILESYSTEM)
            self.assertEqual(res.tool_args["intent"], "DRIVE_OPEN")
            self.assertEqual(res.tool_args["location"], "D:\\")

        # File ops
        res = _try_filesystem("find all PDFs in D:\\")
        self.assertIsNotNone(res)
        self.assertEqual(res.route_type, RouteType.FILESYSTEM)
        self.assertEqual(res.tool_args["intent"], "FILESYSTEM_SEARCH")
        self.assertEqual(res.tool_args["target_name"], "all PDFs")
        self.assertEqual(res.tool_args["location"], "D:\\")
        
    def test_system_info_router(self):
        res = _try_system_info("what time is it")
        self.assertIsNotNone(res)
        self.assertEqual(res.tool_name, "sys_get_time")
        
        res = _try_system_info("how much ram do i have")
        self.assertIsNotNone(res)
        self.assertEqual(res.tool_name, "win_system_info")

if __name__ == "__main__":
    unittest.main()
