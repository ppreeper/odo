#!/usr/bin/env python3
import yaml
import argparse

# TODO: read https://realpython.com/command-line-interfaces-python-argparse/

def do_command_k():
    return

def do_command_j():
    print("do_command_j")
    return

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='Functions')
    parser_1 = subparsers.add_parser('cmd1', help='...')
    parser_1.add_argument('cmd1_option1', type=str, help='...')
    parser_1.set_defaults(parser1=True)

    parser_2 = subparsers.add_parser('cmd2', help='...')
    parser_2.set_defaults(parser2=True)

    parser_3 = subparsers.add_parser('cmd3', help='...')
    parser_3.add_argument('cmd3_options', type=int, help='...')
    parser_3.set_defaults(parser_3=True)

    parser_k = subparsers.add_parser('cmdk', help='...')
    parser_k.set_defaults(func=do_command_k)

    parser_j = subparsers.add_parser('cmdj', help='...')
    parser_j.add_argument('cmdj_options', type=int, help='...')
    parser_j.add_argument('cmdj_options', type=int, help='...')
    parser_j.set_defaults(func=do_command_j)

    args = parser.parse_args()
    print(args)
    if args.func:
        args.func(args)

if __name__=="__main__":
    main()