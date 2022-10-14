from os import path
import sys
from coll_asm_adj_gui.windows import file_loader_dialog
from coll_asm_adj_gui.io import file_reader
from coll_asm_adj_gui.ui import ui_assembly_adjuster_main, custom_control
from coll_asm_adj_gui.adjuster import locator, vis, adjuster
from copy import deepcopy
from PySide2.QtWidgets import QWidget, QFileDialog, QMessageBox


class OptArgs:

    def __init__(self):
        self.src_chr = ""
        self.src_blk = ""
        self.tgt_chr = ""
        self.tgt_blk = ""
        self.is_rev = False


class AssemblyAdjusterMain(QWidget):

    def __init__(self):
        super(AssemblyAdjusterMain, self).__init__()
        self.ui = None
        self.main_window = None
        self.graph_scene = None

        self.opt_method_db = {"Insert front": self.__ins_front,
                              "Insert back": self.__ins_back,
                              "Insert head": self.__ins_head,
                              "Insert tail": self.__ins_tail,
                              "Source chromosome": self.__rev_chr,
                              "Source block": self.__rev_blk,
                              "Swap chromosome": self.__swp_chr,
                              "Swap block": self.__swp_blk}

        self.qry_bed_file = ""
        self.ref_bed_file = ""
        self.anchors_file = ""
        self.qry_agp_file = ""
        self.qry_name = ""
        self.ref_name = ""
        self.pic = ""

        self.qry_chr_list = []

        self.qry_bed_db = None
        self.ref_bed_db = None
        self.gene_pairs = None
        self.qry_agp_db = None
        self.block_regions = None
        self.block_list_db = None
        self.block_detail = None

        self.mpl_vis = vis.VisContent()

        self.adjuster = adjuster.Adjuster()
        self.reader = file_reader.Reader()

        self.init_ui()

    def init_ui(self):
        self.ui = ui_assembly_adjuster_main.Ui_AssemblyAdjusterMain()
        self.ui.setupUi(self)

        self.ui.method_cbox.addItems(self.opt_method_db.keys())
        self.ui.file_loader_btn.clicked.connect(self.load_files)
        self.ui.file_save_btn.clicked.connect(self.save_files)
        self.ui.refresh_btn.clicked.connect(self.show_pic)
        self.ui.mod_btn.clicked.connect(self.modify)
        self.ui.src_chr_cbox.currentTextChanged.connect(self.__add_src_blks)
        self.ui.tgt_chr_cbox.currentTextChanged.connect(self.__add_tgt_blks)
        self.ui.src_blk_cbox.currentTextChanged.connect(self.__add_blk_lst)

    def load_files(self):
        file_loader = file_loader_dialog.FileLoaderDialog(self)
        self.__notify_with_title("Select files")
        file_loader.show()
        file_loader.signal_path.connect(self.get_file_path)

    def save_files(self):
        self.__notify_with_title("Saving files")
        folder_path = QFileDialog.getExistingDirectory(self, "Select folder")
        if folder_path and path.isdir(folder_path):
            self.__notify_with_title("Saving tour files")
            for chrn in self.qry_agp_db:
                tour_file = path.join(folder_path, '%s.tour' % chrn)
                with open(tour_file, 'w') as fout:
                    tour_list = []
                    for _, _, ctg, _, direct in self.qry_agp_db[chrn]:
                        tour_list.append("%s%s" % (ctg, direct))
                    fout.write("%s" % ' '.join(tour_list))

            self.__notify_with_title("Saving figure")
            fig_file = path.join(folder_path, "%s.%s.pdf" % (self.qry_name, self.ref_name))
            self.mpl_vis.figure_content.plt.savefig(fig_file, bbox_inches='tight')

            self.__notify_with_title("Saving blocks")
            block_file = path.join(folder_path, "contig_blocks.txt")
            with open(block_file, 'w') as fout:
                for chrn in sorted(self.mpl_vis.block_list_db):
                    for idx in self.mpl_vis.block_list_db[chrn]:
                        idx = int(idx)-1
                        fout.write(">%s_Block_%d\n%s\n" % (chrn, idx+1, ' '.join(self.mpl_vis.block_detail[idx])))

        QMessageBox.information(self, "Save files", "Tour files saved.")
        self.__notify_with_title("Success")

    def show_pic(self):
        self.__notify_with_title("Drawing")
        blk_loc = locator.Locator()
        blk_loc.convert_anchors(self.qry_bed_db, self.ref_bed_db, self.gene_pairs)
        if self.ui.resolution_text.text():
            resolution = int(float(self.ui.resolution_text.text()))
        else:
            resolution = 20
        if resolution == 0 or resolution == 20:
            resolution = 20
            self.ui.resolution_text.setText("20")
        blk_loc.get_break_blocks(resolution)

        self.mpl_vis.gen_figure(blk_loc.links, blk_loc.block_db, self.qry_agp_db, resolution,
                                self.qry_name, self.ref_name)

        self.block_regions = self.mpl_vis.block_regions
        self.block_list_db = self.mpl_vis.block_list_db
        self.block_detail = self.mpl_vis.block_detail

        self.ui.src_blk_cbox.clear()
        src_chr = self.ui.src_chr_cbox.currentText()
        if src_chr in self.block_list_db:
            self.ui.src_blk_cbox.addItems(self.block_list_db[src_chr])

        self.ui.blk_lst.clear()
        self.ui.blk_lst.addItems(self.block_detail[0])

        self.ui.tgt_blk_cbox.clear()
        if self.ui.tgt_chr_cbox.currentText() in self.block_list_db:
            self.ui.tgt_blk_cbox.addItems(self.block_list_db[self.ui.tgt_chr_cbox.currentText()])
        if not self.graph_scene:
            self.graph_scene = custom_control.ControlGraphicsScene()
            self.graph_scene.addWidget(self.mpl_vis.figure_content)
            self.ui.plot_viewer.setScene(self.graph_scene)
            self.ui.plot_viewer.show()
        else:
            self.mpl_vis.figure_content.draw()
        self.__notify_with_title("Success")

    def get_file_path(self, content):
        if content:
            self.qry_bed_file, self.ref_bed_file, self.anchors_file, self.qry_agp_file = content
            if path.isfile(self.qry_bed_file) and path.isfile(self.ref_bed_file) and \
                    path.isfile(self.anchors_file) and path.isfile(self.qry_agp_file):
                self.__notify_with_title("Loading files")

                if self.__load_file():
                    self.__add_options()
                    self.show_pic()
                    self.__notify_with_title("Files loaded")
                else:
                    QMessageBox.critical(self, 'Error', 'Cannot load files, please check input files!')
                    self.__notify_with_title("Files load failed")
                    return
                self.__enable_controls()
            else:
                self.__notify_with_title()
        else:
            self.__notify_with_title()

    def modify(self):
        self.ui.mod_btn.setEnabled(False)
        args = OptArgs()

        args.src_chr = self.ui.src_chr_cbox.currentText()
        args.src_blk = int(self.ui.src_blk_cbox.currentText()) - 1
        args.tgt_chr = self.ui.tgt_chr_cbox.currentText()
        args.tgt_blk = int(self.ui.tgt_blk_cbox.currentText()) - 1
        args.is_rev = self.ui.rev_chk.isChecked()
        opt = self.ui.method_cbox.currentText()

        self.__notify_with_title(opt)

        if opt in self.opt_method_db:
            self.opt_method_db[opt](args)

            self.show_pic()
            self.ui.mod_btn.setEnabled(True)

        self.__notify_with_title("Success")

    def __rev_chr(self, args):
        if not args.is_rev:
            return
        tmp_dict = deepcopy(self.qry_agp_db)
        tmp_dict[args.src_chr] = self.adjuster.reverse_chr(tmp_dict[args.src_chr])
        self.qry_bed_db = self.adjuster.trans_anno(self.qry_agp_db, tmp_dict, self.qry_bed_db)
        self.qry_agp_db = deepcopy(tmp_dict)
        del tmp_dict

    def __rev_blk(self, args):
        if not args.is_rev:
            return
        tmp_dict = deepcopy(self.qry_agp_db)
        tmp_dict[args.src_chr] = self.adjuster.reverse_block(tmp_dict[args.src_chr], self.block_regions[args.src_blk])
        self.qry_bed_db = self.adjuster.trans_anno(self.qry_agp_db, tmp_dict, self.qry_bed_db)
        self.qry_agp_db = deepcopy(tmp_dict)
        del tmp_dict

    def __ins_head(self, args):
        tmp_dict = deepcopy(self.qry_agp_db)
        tmp_dict[args.src_chr], extract_agp_list = self.adjuster.split_block(tmp_dict[args.src_chr],
                                                                        self.block_regions[args.src_blk])
        if args.is_rev:
            extract_agp_list = self.adjuster.reverse_chr(extract_agp_list)

        tmp_dict[args.tgt_chr] = self.adjuster.ins_term(tmp_dict[args.tgt_chr], extract_agp_list)
        self.qry_bed_db = self.adjuster.trans_anno(self.qry_agp_db, tmp_dict, self.qry_bed_db)
        self.qry_agp_db = deepcopy(tmp_dict)
        del tmp_dict

    def __ins_tail(self, args):
        tmp_dict = deepcopy(self.qry_agp_db)
        tmp_dict[args.src_chr], extract_agp_list = self.adjuster.split_block(tmp_dict[args.src_chr],
                                                                             self.block_regions[args.src_blk])
        if args.is_rev:
            extract_agp_list = self.adjuster.reverse_chr(extract_agp_list)

        tmp_dict[args.tgt_chr] = self.adjuster.ins_term(tmp_dict[args.tgt_chr], extract_agp_list, False)
        self.qry_bed_db = self.adjuster.trans_anno(self.qry_agp_db, tmp_dict, self.qry_bed_db)
        self.qry_agp_db = deepcopy(tmp_dict)
        del tmp_dict

    def __ins_front(self, args):
        tmp_dict = deepcopy(self.qry_agp_db)
        tmp_dict[args.src_chr], extract_agp_list = self.adjuster.split_block(tmp_dict[args.src_chr],
                                                                             self.block_regions[args.src_blk])
        if args.is_rev:
            extract_agp_list = self.adjuster.reverse_chr(extract_agp_list)

        tmp_dict[args.tgt_chr] = self.adjuster.ins_pos(tmp_dict[args.tgt_chr], extract_agp_list,
                                                       self.block_regions[args.tgt_blk])
        self.qry_bed_db = self.adjuster.trans_anno(self.qry_agp_db, tmp_dict, self.qry_bed_db)
        self.qry_agp_db = deepcopy(tmp_dict)
        del tmp_dict

    def __ins_back(self, args):
        tmp_dict = deepcopy(self.qry_agp_db)
        tmp_dict[args.src_chr], extract_agp_list = self.adjuster.split_block(tmp_dict[args.src_chr],
                                                                             self.block_regions[args.src_blk])
        if args.is_rev:
            extract_agp_list = self.adjuster.reverse_chr(extract_agp_list)

        tmp_dict[args.tgt_chr] = self.adjuster.ins_pos(tmp_dict[args.tgt_chr], extract_agp_list,
                                                       self.block_regions[args.tgt_blk],
                                                       False)
        self.qry_bed_db = self.adjuster.trans_anno(self.qry_agp_db, tmp_dict, self.qry_bed_db)
        self.qry_agp_db = deepcopy(tmp_dict)
        del tmp_dict

    def __swp_chr(self, args):
        if args.src_chr != args.tgt_chr:
            tmp_dict = deepcopy(self.qry_agp_db)
            tmp_list = deepcopy(tmp_dict[args.src_chr])
            tmp_dict[args.src_chr] = deepcopy(tmp_dict[args.tgt_chr])
            tmp_dict[args.tgt_chr] = deepcopy(tmp_list)

            self.qry_bed_db = self.adjuster.trans_anno(self.qry_agp_db, tmp_dict, self.qry_bed_db)
            self.qry_agp_db = deepcopy(tmp_dict)
            del tmp_dict, tmp_list

    def __swp_blk(self, args):
        if args.src_blk != args.tgt_blk:
            if args.src_chr != args.tgt_chr:
                tmp_dict = deepcopy(self.qry_agp_db)
                tmp_dict[args.tgt_chr], tmp_dict[args.src_chr] = self.adjuster.swap_blk_diff_chr(tmp_dict[args.src_chr],
                                                                                                 self.block_regions[
                                                                                                     args.src_blk],
                                                                                                 tmp_dict[args.tgt_chr],
                                                                                                 self.block_regions[
                                                                                                     args.tgt_blk])

                self.qry_bed_db = self.adjuster.trans_anno(self.qry_agp_db, tmp_dict, self.qry_bed_db)
                self.qry_agp_db = deepcopy(tmp_dict)

                del tmp_dict
            else:
                tmp_dict = deepcopy(self.qry_agp_db)
                tmp_dict[args.src_chr] = self.adjuster.swap_blk_single_chr(tmp_dict[args.src_chr],
                                                                           self.block_regions[args.src_blk],
                                                                           self.block_regions[args.tgt_blk])
                if not tmp_dict[args.src_chr]:
                    return
                self.qry_bed_db = self.adjuster.trans_anno(self.qry_agp_db, tmp_dict, self.qry_bed_db)
                self.qry_agp_db = deepcopy(tmp_dict)

                del tmp_dict

    def __load_file(self):
        if '/' in self.qry_bed_file:
            sep = '/'
        else:
            sep = '\\'
        self.qry_name = self.qry_bed_file.split(sep)[-1].split('.')[0]
        self.ref_name = self.ref_bed_file.split(sep)[-1].split('.')[0]
        try:
            self.qry_chr_list, self.qry_bed_db = self.reader.read_bed(self.qry_bed_file)
            if not self.qry_bed_db:
                return False

            _, self.ref_bed_db = self.reader.read_bed(self.ref_bed_file)
            if not self.ref_bed_db:
                return False

            self.gene_pairs = self.reader.read_anchors(self.anchors_file)
            if not self.gene_pairs:
                return False

            self.qry_agp_db = self.reader.read_agp(self.qry_agp_file)
            if not self.qry_agp_db:
                return False
        except IndexError:
            return False
        return True

    def __enable_controls(self):
        self.ui.file_save_btn.setEnabled(True)
        self.ui.blk_lst.setEnabled(True)
        self.ui.mod_btn.setEnabled(True)
        self.ui.refresh_btn.setEnabled(True)
        self.ui.src_chr_cbox.setEnabled(True)
        self.ui.src_blk_cbox.setEnabled(True)
        self.ui.tgt_chr_cbox.setEnabled(True)
        self.ui.tgt_blk_cbox.setEnabled(True)
        self.ui.method_cbox.setEnabled(True)
        self.ui.rev_chk.setEnabled(True)
        self.ui.plot_viewer.setEnabled(True)

    def __add_options(self):
        self.ui.src_chr_cbox.addItems(self.qry_chr_list)
        self.ui.tgt_chr_cbox.addItems(self.qry_chr_list)

    def __add_src_blks(self, value):
        self.ui.src_blk_cbox.clear()
        if self.block_list_db and value in self.block_list_db:
            self.ui.src_blk_cbox.addItems(self.block_list_db[value])

    def __add_tgt_blks(self, value):
        self.ui.tgt_blk_cbox.clear()
        if self.block_list_db and value in self.block_list_db:
            self.ui.tgt_blk_cbox.addItems(self.block_list_db[value])

    def __add_blk_lst(self, value):
        self.ui.blk_lst.clear()
        if value:
            self.ui.blk_lst.addItems(self.block_detail[int(value) - 1])

    def __notify_with_title(self, info=""):
        if info:
            self.setWindowTitle("Manual Collinearity Assembly Adjuster - %s" % info)
        else:
            self.setWindowTitle("Manual Collinearity Assembly Adjuster")

    def closeEvent(self, event):
        sys.exit(0)
