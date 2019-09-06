import jpype
jpype.startJVM(jpype.getDefaultJVMPath())
jpype.java.lang.System.out.println('Hello World!')
