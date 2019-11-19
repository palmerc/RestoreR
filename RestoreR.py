import collections

from antlr4 import InputStream, ParseTreeWalker

from JavaLexer import JavaLexer, CommonTokenStream
from JavaParser import JavaParser
from RFileParserListener import RFileParserListener
from RValueReplacementListener import  RValueReplacementListener

import os
import argparse


def find_files(path, Extension='.java'):
    files = []
    for (dirpath, dirnames, filenames) in os.walk(path):
        for filename in filenames:
            base, ext = os.path.splitext(filename)
            if ext == Extension:
                fq_path = os.path.join(dirpath, filename)
                files.append(fq_path)

    return files

def parse_file(path):
    file = open(path, 'r').read()

    codeStream = InputStream(file)
    lexer = JavaLexer(codeStream)

    # First lexing way
    tokens = CommonTokenStream(lexer)
    parser = JavaParser(tokens)
    parser.buildParseTrees = True

    return parser


def main():
    parser = argparse.ArgumentParser(description='Restore R Values in Android Code')
    parser.add_argument('-i', dest='add_r_import', action='store_true', help='add import for R into java files')
    parser.add_argument('-r', dest='r_file', required=True, help='specify location of R java file')
    parser.add_argument('-p', '--project', required=True, dest='j_files',
                        help='specify location of Android project')
    parser.add_argument('--overwrite', dest='overwrite', action='store_true',
                        help='overwrite the source files with the new values')
    args = parser.parse_args()

    r_parser = parse_file(args.r_file)
    r_tree = r_parser.compilationUnit()

    r_listener = RFileParserListener()
    r_walker = ParseTreeWalker()
    r_walker.walk(r_listener, r_tree)

    for key, value in r_listener.r_mapping.items():
        print(hex(key).upper() + " = " + value)

    java_files = find_files(args.j_files)

    j_walker = ParseTreeWalker()

    Interval = collections.namedtuple('Interval', ['start', 'stop'])

    replacements = 0
    for path in java_files:
        if os.path.basename(path) == 'R.java':
            continue

        print("First pass: {}".format(path))
        first_pass_parser = parse_file(path)
        first_pass_listener = RValueReplacementListener(first_pass_parser.getTokenStream())
        first_pass_listener.r_mapping = r_listener.r_mapping

        first_pass_tree = first_pass_parser.compilationUnit()
        j_walker.walk(first_pass_listener, first_pass_tree)
        replacement_count = first_pass_listener.replacements
        if replacement_count > 0:
            print("Identified {} hex values to be replaced.".format(replacement_count))
        else:
            continue

        print("Rewriting tokens")
        rewrite_parser = parse_file(path)
        rewrite_listener = RValueReplacementListener(rewrite_parser.getTokenStream())
        rewrite_listener.r_mapping = r_listener.r_mapping

        rewrite_tree = rewrite_parser.compilationUnit()
        j_walker.walk(first_pass_listener, rewrite_tree)

        if args.add_r_import:
            rewrite_listener.r_package = r_listener.package

        rewrite_tree = rewrite_parser.compilationUnit()
        j_walker.walk(rewrite_listener, rewrite_tree)

        rewriter = rewrite_listener.rewriter
        interval = Interval(0, len(rewriter.tokens.tokens) - 1)
        j_rewritten = rewriter.getText(rewriter.DEFAULT_PROGRAM_NAME, interval)
        if args.overwrite:
            print("Overwriting file: {}".format(path))
            f = open(path, 'w')
            f.write(j_rewritten)
        else:
            print(j_rewritten)

        replacements += rewrite_listener.replacements

    print('Replaced ' + str(replacements) + ' hex values.')


if __name__ == '__main__':
    main()
