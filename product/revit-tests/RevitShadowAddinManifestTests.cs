using System.Xml.Linq;
using Xunit;

namespace RevitShadow.Tests;

public sealed class RevitShadowAddinManifestTests
{
    [Fact]
    public void DevelopmentCommandTemplateHasStableRevitContract()
    {
        var templatePath = Path.Combine(AppContext.BaseDirectory, "RevitShadow.addin.template");
        var addIns = XDocument.Load(templatePath).Root?.Elements("AddIn").ToArray();
        var addIn = addIns?[0];

        Assert.Equal(2, addIns?.Length);
        Assert.NotNull(addIn);
        Assert.Equal("Command", (string?)addIn.Attribute("Type"));
        Assert.Equal("Dynamo Shadow Project Context Smoke Test", (string?)addIn.Element("Text"));
        Assert.Equal("RevitShadow.ForwardProjectContextSmokeCommand", (string?)addIn.Element("FullClassName"));
        Assert.Equal("__REVIT_SHADOW_ASSEMBLY__", (string?)addIn.Element("Assembly"));
        Assert.Equal("F39416B1-9B93-4E7C-AC9B-3855E524670C", (string?)addIn.Element("AddInId"));
        Assert.Equal("DYSH", (string?)addIn.Element("VendorId"));

        var fullForward = addIns?[1];
        Assert.Equal("Dynamo Shadow Full Forward Development Smoke Test", (string?)fullForward?.Element("Text"));
        Assert.Equal("RevitShadow.ForwardFullForwardSmokeCommand", (string?)fullForward?.Element("FullClassName"));
        Assert.Equal("__REVIT_SHADOW_ASSEMBLY__", (string?)fullForward?.Element("Assembly"));
        Assert.Equal("88F33200-E215-45C6-B244-F130FDB80959", (string?)fullForward?.Element("AddInId"));
        Assert.Equal("DYSH", (string?)fullForward?.Element("VendorId"));
    }
}
