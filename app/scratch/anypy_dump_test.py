from resources.AnyPyTools.anypytools import AnyPyProcess
from resources.AnyPyTools.anypytools import AnyMacro
from resources.AnyPyTools.anypytools import tools
from resources.AnyPyTools.anypytools.macro_commands import (MacroCommand, Load, SetValue, SetValue_random,  Dump,
                                                            SaveDesign, LoadDesign, SaveValues, LoadValues,
                                                            UpdateValues, SaveData, OperationRun)
import os


cwd = os.getcwd()
os.chdir('D:\\RobinSean\\Sean\\5. Master\\Projekt CSE\\Interpolation_Validierung\\anybody\\')
print(os.getcwd())
# patella_tendon_lengths = [
#     0.02 + i*0.01
#     for i in range(7)
# ]
# print(patella_tendon_lengths)

app = AnyPyProcess(num_processes=1,
                   return_task_info=True,
                   anybodycon_path="C:/Program Files/AnyBody Technology/AnyBody.7.1/AnyBodyCon.exe")
# macrolist = [
#     Load('Knee.any'),
#     # SetValue('Main.MyModel.PatellaLigament.DriverPos', patella_tendon_lengths ),
#     SetValue('Main.MyStudy.tStart', 1),
#     SetValue('Main.MyStudy.tEnd', 2),
#     OperationRun('Main.MyStudy.InitialConditions'),
#     OperationRun('Main.MyStudy.Kinematics'),
#     OperationRun('Main.MyStudy.InverseDynamics'),
#     # Dump('Main.MyStudy.Output.Abscissa.t'),
#     # Dump('Main.MyStudy.Output.MaxMuscleActivity'),
#     # Dump('Main.MyModel.PatellaLigament.DriverPos'),
# ]

macrolist = [
    Load('HAND.Main.any'),
    SetValue('Main.Study.nStep', 5),
    Dump('Main.HumanModel.Mannequin.Posture.Right.Finger1.CMCFlexionVec')
    # OperationRun('Main.RunMotionAndParameterOptimizationSequence')
    # OperationRun('Main.MyStudy.InverseDynamics'),
]
output = app.start_macro(macrolist)


print(output['Main.HumanModel.Mannequin.Posture.Right.Finger1.CMCFlexionVec'])
# parameter_study_macro = AnyMacro(macro, number_of_macros= len(patella_tendon_lengths))

os.chdir(cwd)